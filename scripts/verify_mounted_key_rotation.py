"""Linux mounted-key rotation/recovery fixture; no hosted key custody claim."""
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ha.connected.document_configuration import MountedKeys
from ha.connected.spaces_storage import SpacesObjects
from ha.connected.tax_snapshot import encode_snapshot,decode_snapshot

class FictionalVersionedStorage:
    def __init__(self):self.objects={}
    def put_object(self,**request):
        if request['ACL']!='private':raise ValueError('Private fixture required')
        version=uuid.uuid4().hex
        self.objects[(request['Key'],version)]=request['Body']
        return {'VersionId':version}
    def get_object(self,**request):
        return {'VersionId':request['VersionId'],'Body':BytesIO(self.objects[(request['Key'],request['VersionId'])])}


def main():
    if os.name!='posix':raise ValueError('Actual Linux key permissions required')
    with tempfile.TemporaryDirectory(prefix='ha-key-rotation-') as temp:
        root=Path(temp);root.chmod(0o700)
        live=root/'mounted';recovery=root/'separate-recovery';restored=root/'restored'
        for directory in (live,recovery,restored):directory.mkdir(mode=0o700)
        for name in ('original-key','rotated-key'):
            path=live/(name+'.key');path.write_bytes(AESGCM.generate_key(bit_length=256));path.chmod(0o600)
            copy=recovery/path.name;shutil.copyfile(path,copy);copy.chmod(0o600)
        store=FictionalVersionedStorage();keys=MountedKeys(live)
        old=SpacesObjects(store,'fictional-private','original-key',keys)
        first='documents/'+str(uuid.uuid4());second='documents/'+str(uuid.uuid4())
        original=old.put(first,b'Fictional original tax document','text/plain')
        tax_input={'year':'2026','profile':{'firstName':'Fictional original'},
            'forms':[{'layout':'standard','box1':'001.20','box2':'','states':[{'state':'LA'},{'state':'TX'}]}],
            'active':0,'stateAnswers':{}}
        original_tax_key='documents/'+str(uuid.uuid4())
        original_tax_version=old.put(original_tax_key,encode_snapshot(tax_input,2026),'text/plain')
        changed_input=json.loads(json.dumps(tax_input));changed_input['forms'][0]['box1']='200.00'
        rotated=SpacesObjects(store,'fictional-private','rotated-key',keys)
        changed_tax_key='documents/'+str(uuid.uuid4())
        changed_tax_version=rotated.put(changed_tax_key,encode_snapshot(changed_input,2026),'text/plain')
        correction=rotated.put(second,b'Fictional corrected tax document','text/plain')
        if rotated.get(first,original)!=b'Fictional original tax document' or rotated.get(second,correction)!=b'Fictional corrected tax document':
            raise ValueError('Rotation did not preserve exact bytes')
        (live/'original-key.key').unlink()
        try:rotated.get(first,original)
        except ValueError:pass
        else:raise ValueError('Missing historical key accepted')
        if rotated.get(second,correction)!=b'Fictional corrected tax document':raise ValueError('Active key read failed')
        for path in recovery.iterdir():
            copy=restored/path.name;shutil.copyfile(path,copy);copy.chmod(0o600)
        recovered=SpacesObjects(store,'fictional-private','rotated-key',MountedKeys(restored))
        if recovered.get(first,original)!=b'Fictional original tax document' or recovered.get(second,correction)!=b'Fictional corrected tax document':
            raise ValueError('Recovered key set failed')
        if (decode_snapshot(recovered.get(original_tax_key,original_tax_version),2026)!=tax_input
                or decode_snapshot(recovered.get(changed_tax_key,changed_tax_version),2026)!=changed_input):
            raise ValueError('Recovered encoded tax inputs differ')
        key_path=restored/'original-key.key';key_path.chmod(0o644)
        try:recovered.get(first,original)
        except ValueError:pass
        else:raise ValueError('Broad key permissions accepted')
        key_path.chmod(0o600);key_path.unlink();key_path.symlink_to(recovery/'original-key.key')
        try:recovered.get(first,original)
        except ValueError:pass
        else:raise ValueError('Key symlink accepted')
        if any(b'Fictional' in payload for payload in store.objects.values()):raise ValueError('Plaintext object found')
        report={'environment':'actual Linux filesystem with fictional SDK storage',
            'rotation_exact_original_correction':'passed','encoded_tax_inputs_exact_after_key_recovery':'passed',
            'tax_scope':'codec and encrypted adapter only; database and MFA not part of this probe','missing_historical_key_denied':True,
            'active_key_remains_readable':True,'separate_fixture_key_copy_recovery':'passed',
            'broad_permissions_and_symlink_denied':True,'plaintext_absent_from_objects':True,
            'hosted_spaces':'not_run','external_key_custody':'not_verified'}
        (Path(__file__).resolve().parents[1]/'docs/KEY-ROTATION-EVIDENCE.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report))

if __name__=='__main__':main()
