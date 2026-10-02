"""Separate connected-service entry point; unconfigured preview never authenticates."""
import argparse
import os
import ssl
from .api import create_server
from .auth import Sessions, TokenVerifier
from .oauth import CognitoLogin
from .postgres import PostgresRepository, PostgresLedger


def build_server(address, origin, environment=None):
    env = os.environ if environment is None else environment
    provider = env.get('HA_AUTH_PROVIDER', 'disabled')
    if provider not in ('disabled', 'cognito', 'keycloak'):
        raise ValueError('Unsupported authentication provider')
    required = ('HA_DATABASE_URL', 'HA_AWS_REGION', 'HA_COGNITO_POOL',
                'HA_COGNITO_CLIENT', 'HA_COGNITO_DOMAIN')
    cognito_names=required[1:]
    keycloak_names=('HA_KEYCLOAK_ISSUER','HA_KEYCLOAK_CLIENT')
    present = [bool(env.get(name)) for name in required]
    login = ledger = None
    if provider == 'cognito' and not all(present):
        raise ValueError('Connected configuration is incomplete')
    if provider == 'keycloak' and (not all(env.get(name) for name in ('HA_DATABASE_URL',*keycloak_names)) or any(env.get(name) for name in cognito_names)):
        raise ValueError('Keycloak configuration is incomplete or mixed with Cognito')
    if provider == 'cognito' and any(env.get(name) for name in keycloak_names):
        raise ValueError('Authentication providers cannot be mixed')
    if provider == 'disabled' and (any(present) or any(env.get(name) for name in keycloak_names)):
        raise ValueError('Select an authentication provider explicitly')
    if provider == 'cognito':
        import boto3
        import jwt
        region, pool = env['HA_AWS_REGION'], env['HA_COGNITO_POOL']
        issuer = f'https://cognito-idp.{region}.amazonaws.com/{pool}'
        keys = jwt.PyJWKClient(issuer + '/.well-known/jwks.json')
        verifier = TokenVerifier(issuer, env['HA_COGNITO_CLIENT'],
                                 lambda token: keys.get_signing_key_from_jwt(token).key)
        login = CognitoLogin(boto3.client('cognito-idp', region_name=region), pool,
                            env['HA_COGNITO_CLIENT'], env['HA_COGNITO_DOMAIN'],
                            origin + '/api/auth/callback', verifier)
        ledger = PostgresLedger(PostgresRepository(env['HA_DATABASE_URL']))
    if provider == 'keycloak':
        import jwt
        from .keycloak import KeycloakVerifier,KeycloakLogin,validate_issuer
        issuer=validate_issuer(env['HA_KEYCLOAK_ISSUER'])
        keys=jwt.PyJWKClient(issuer+'/protocol/openid-connect/certs')
        verifier=KeycloakVerifier(issuer,env['HA_KEYCLOAK_CLIENT'],
                                  lambda token:keys.get_signing_key_from_jwt(token).key)
        login=KeycloakLogin(issuer,env['HA_KEYCLOAK_CLIENT'],origin+'/api/auth/callback',verifier)
        ledger=PostgresLedger(PostgresRepository(env['HA_DATABASE_URL']))
    # Private uploads stay unavailable until an actual scanning provider is wired.
    return create_server(address, Sessions(), ledger, None, login, origin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--origin', default='https://localhost:8766')
    parser.add_argument('--certificate')
    parser.add_argument('--key')
    parser.add_argument('--behind-https-proxy', action='store_true',
                        help='Only for a platform whose public ingress enforces HTTPS')
    args = parser.parse_args()
    if bool(args.certificate) != bool(args.key):
        parser.error('Supply both certificate and key')
    if args.host not in ('127.0.0.1', 'localhost') and not (args.certificate or args.behind_https_proxy):
        parser.error('Direct remote listening requires TLS')
    server = build_server((args.host, args.port), args.origin)
    if args.certificate:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(args.certificate, args.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    print('Connected service listening; configuration does not prove deployment readiness.', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
