"""Download a checksum-verified official Keycloak distribution for local tests.

No admin user, credentials, realm or running service is created.
"""
import hashlib
import json
import os
import tempfile
import stat
from pathlib import Path,PurePosixPath
import urllib.request
import zipfile

VERSION='26.8.0'
ROOT=Path(__file__).resolve().parents[1]

def main():
    name='keycloak-'+VERSION+'.zip'
    request=urllib.request.Request('https://api.github.com/repos/keycloak/keycloak/releases/tags/'+VERSION,
        headers={'User-Agent':'HA-local-verification','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=30) as response:
        release=json.load(response)
    if release.get('tag_name')!=VERSION or release.get('draft') or release.get('prerelease'):
        raise ValueError('Stable official release required')
    matches=[item for item in release['assets'] if item['name']==name]
    if len(matches)!=1:raise ValueError('Official distribution asset unavailable')
    asset=matches[0];digest=asset.get('digest','')
    if not digest.startswith('sha256:') or len(digest)!=71:
        raise ValueError('Official asset checksum required')
    url='https://github.com/keycloak/keycloak/releases/download/'+VERSION+'/'+name
    if asset['browser_download_url']!=url:raise ValueError('Unexpected distribution URL')
    folder=ROOT/'.connected-local'/'keycloak';folder.mkdir(exist_ok=True)
    archive=folder/name
    if not archive.exists():
        with tempfile.TemporaryDirectory(prefix='download-',dir=folder) as staging:
            pending=Path(staging)/name
            with urllib.request.urlopen(url,timeout=60) as response,pending.open('xb') as output:
                while chunk:=response.read(1024*1024):output.write(chunk)
            with pending.open('rb') as handle:
                if digest!='sha256:'+hashlib.file_digest(handle,'sha256').hexdigest():
                    raise ValueError('Distribution checksum mismatch')
            os.link(pending,archive)
    with archive.open('rb') as handle:
        actual=hashlib.file_digest(handle,'sha256').hexdigest()
    if digest!='sha256:'+actual:raise ValueError('Cached distribution checksum mismatch')
    target=folder/('keycloak-'+VERSION)
    marker=target/'.ha-source-sha256'
    if target.exists():
        if not marker.is_file() or marker.read_text(encoding='utf-8')!=actual:
            raise ValueError('Existing distribution has no verified completion marker; use a fresh test directory')
    else:
        with tempfile.TemporaryDirectory(prefix='extract-',dir=folder) as staging:
            with zipfile.ZipFile(archive) as source:
                for member in source.infolist():
                    path=PurePosixPath(member.filename)
                    if (not path.parts or path.is_absolute() or '..' in path.parts
                            or path.parts[0]!=target.name
                            or stat.S_ISLNK(member.external_attr>>16)):
                        raise ValueError('Unexpected distribution path')
                source.extractall(staging)
            extracted=Path(staging)/target.name
            (extracted/'.ha-source-sha256').write_text(actual,encoding='utf-8')
            extracted.rename(target)
    report={'version':VERSION,'official_download':url,'sha256':actual,
        'checksum_match':True,'identity_service_started':False,'mfa_verified':False}
    (ROOT/'docs/KEYCLOAK-DISTRIBUTION-EVIDENCE.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':main()
