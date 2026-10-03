import contextlib
import io
import json
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace
from scripts.check_spaces_configuration import check_configuration,main,make_client


class Client:
    def __init__(self,status='Enabled',grants=None):
        self.calls=[];self.status=status
        self.grants=grants if grants is not None else [{'Grantee':{'Type':'CanonicalUser','ID':'fictional-owner'},'Permission':'FULL_CONTROL'}]
    def get_bucket_versioning(self,**kwargs):
        self.calls.append(('versioning',kwargs));return {'Status':self.status}
    def get_bucket_acl(self,**kwargs):
        self.calls.append(('acl',kwargs));return {'Owner':{'ID':'fictional-owner'},'Grants':self.grants}


class SpacesPreflightTests(unittest.TestCase):
    def test_actual_sdk_serializes_only_guarded_gets_with_synthetic_transport(self):
        from botocore.awsrequest import AWSResponse
        env={'HA_SPACES_REGION':'nyc3','HA_SPACES_BUCKET':'fictional-ha','HA_SPACES_ACCESS_KEY':'fictional-access','HA_SPACES_SECRET_KEY':'fictional-secret'}
        client=make_client(env);seen=[]
        def response(request,**kwargs):
            seen.append((request.method,request.url))
            if request.url.endswith('?versioning'):
                raw=b'<VersioningConfiguration><Status>Enabled</Status></VersioningConfiguration>'
            else:
                raw=b'<AccessControlPolicy xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><Owner><ID>fictional-owner</ID></Owner><AccessControlList><Grant><Grantee xsi:type="CanonicalUser"><ID>fictional-owner</ID></Grantee><Permission>FULL_CONTROL</Permission></Grant></AccessControlList></AccessControlPolicy>'
            return AWSResponse(request.url,200,{},SimpleNamespace(stream=lambda:[raw]))
        client.meta.events.register('before-send.s3',response)
        self.assertTrue(check_configuration(client,'fictional-ha')['configuration_checks_passed'])
        self.assertEqual(seen,[('GET','https://nyc3.digitaloceanspaces.com/fictional-ha?versioning'),('GET','https://nyc3.digitaloceanspaces.com/fictional-ha?acl')])

    def test_sdk_uses_explicit_credentials_verified_endpoint_and_request_guard(self):
        env={'HA_SPACES_REGION':'nyc3','HA_SPACES_BUCKET':'fictional-ha','HA_SPACES_ACCESS_KEY':'fictional-access','HA_SPACES_SECRET_KEY':'fictional-secret'}
        client=Mock()
        with patch('boto3.client',return_value=client) as create:
            self.assertIs(make_client(env),client)
        settings=create.call_args.kwargs
        self.assertEqual(settings['endpoint_url'],'https://nyc3.digitaloceanspaces.com')
        self.assertTrue(settings['verify']);self.assertEqual(settings['aws_access_key_id'],'fictional-access')
        self.assertEqual(settings['aws_secret_access_key'],'fictional-secret')
        self.assertEqual(settings['config'].s3,{'addressing_style':'path'})
        _,guard=client.meta.events.register.call_args.args
        for query in ('acl','versioning'):
            guard(SimpleNamespace(url='https://nyc3.digitaloceanspaces.com/fictional-ha?'+query,method='GET'))
        for url in ('https://s3.amazonaws.com/fictional-ha?acl','http://nyc3.digitaloceanspaces.com/fictional-ha?acl',
                    'https://nyc3.digitaloceanspaces.com/other?acl','https://nyc3.digitaloceanspaces.com/fictional-ha?delete'):
            with self.assertRaises(ValueError):guard(SimpleNamespace(url=url,method='GET'))
        with self.assertRaises(ValueError):guard(SimpleNamespace(url='https://nyc3.digitaloceanspaces.com/fictional-ha?acl',method='PUT'))

    def test_only_reads_versioning_and_owner_acl_without_printing_identifiers(self):
        client=Client();result=check_configuration(client,'fictional-ha')
        self.assertTrue(result['versioning_enabled']);self.assertTrue(result['bucket_acl_owner_only'])
        self.assertTrue(result['configuration_checks_passed'])
        self.assertEqual(client.calls,[('versioning',{'Bucket':'fictional-ha'}),('acl',{'Bucket':'fictional-ha'})])
        self.assertNotIn('fictional',json.dumps(result));self.assertFalse(result['private_objects_verified'])
        self.assertFalse(result['recovery_verified']);self.assertFalse(result['resources_changed'])

    def test_disabled_versioning_or_nonowner_acl_fails_gate(self):
        for status in (None,'Suspended','enabled'):
            self.assertFalse(check_configuration(Client(status),'fictional-ha')['configuration_checks_passed'])
        for grantee in ({'Type':'Group','URI':'http://acs.amazonaws.com/groups/global/AllUsers'},
                        {'Type':'CanonicalUser','ID':'fictional-other'}):
            result=check_configuration(Client(grants=[{'Grantee':grantee,'Permission':'READ'}]),'fictional-ha')
            self.assertFalse(result['bucket_acl_owner_only']);self.assertFalse(result['configuration_checks_passed'])

    def test_missing_or_malformed_owner_grants_fail_closed(self):
        for grants in ([],[{}],[{'Grantee':{'ID':'fictional-owner'},'Permission':'FULL_CONTROL'}],
                       [{'Grantee':{'Type':'CanonicalUser','ID':'fictional-owner'},'Permission':'UNRECOGNIZED'}]):
            self.assertFalse(check_configuration(Client(grants=grants),'fictional-ha')['configuration_checks_passed'])

    def test_invalid_bucket_is_rejected_before_provider_call(self):
        client=Client()
        for bucket in ('https://example.invalid','bad/bucket','../fictional','x'):
            with self.assertRaises(ValueError):check_configuration(client,bucket)
        self.assertEqual(client.calls,[])

    def test_missing_configuration_never_constructs_sdk_or_claims_readiness(self):
        output=io.StringIO()
        with patch.dict('os.environ',{},clear=True),patch('scripts.check_spaces_configuration.make_client') as create,contextlib.redirect_stdout(output):
            self.assertEqual(main(),2)
        create.assert_not_called();result=json.loads(output.getvalue())
        self.assertEqual(result['status'],'configuration_not_supplied');self.assertFalse(result['configuration_checks_passed'])

    def test_provider_exception_is_sanitized(self):
        output=io.StringIO()
        env={'HA_SPACES_REGION':'nyc3','HA_SPACES_BUCKET':'fictional-ha','HA_SPACES_ACCESS_KEY':'fictional-access','HA_SPACES_SECRET_KEY':'fictional-secret'}
        with patch.dict('os.environ',env,clear=True),patch('scripts.check_spaces_configuration.make_client',side_effect=RuntimeError('fictional-secret')),contextlib.redirect_stdout(output):
            self.assertEqual(main(),2)
        self.assertNotIn('fictional-secret',output.getvalue());self.assertEqual(json.loads(output.getvalue())['status'],'configuration_check_unavailable')
