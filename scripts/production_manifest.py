"""Hash published standalone-Flasher assets; never infer firmware source or approval."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def release(repo, tag):
    return json.loads(gh('api', f'repos/{repo}/releases/tags/{quote(tag, safe="")}'))


def select_assets(data):
    tag = data['tag_name']
    if data['draft'] or data['prerelease']:
        raise ValueError('Only published, non-prerelease firmware is accepted.')
    if not re.fullmatch(r'v?\d+\.\d+(?:\.\d+)?', tag):
        raise ValueError('Use a numeric version tag such as v3.4 or v3.4.1.')
    version = tag.removeprefix('v')
    dat = 'apt-' + version.replace('.', '-') + '.dat'
    assets = data['assets']
    selected = []
    for name in (dat, 'pt.cfg'):
        matches = [a for a in assets if a['name'] == name and a['state'] == 'uploaded']
        if len(matches) != 1:
            raise ValueError(f'Attach exactly one {name} to release {tag} before running.')
        selected.extend(matches)
    projects = [a for a in assets if a['name'].endswith('.jflash')]
    if len(projects) > 1:
        raise ValueError('Attach at most one matching .jflash project.')
    if projects and projects[0]['state'] != 'uploaded':
        raise ValueError('J-Flash project upload is incomplete.')
    return version, selected + projects


def build_manifest(repo, data, folder):
    version, selected = select_assets(data)
    files = []
    for asset in selected:
        name = asset['name']
        if Path(name).name != name or not re.fullmatch(r'[A-Za-z0-9_.-]+', name):
            raise ValueError('Asset filename must be a simple filename.')
        path = folder / name
        if not path.is_file() or path.stat().st_size != asset['size'] or not asset['size']:
            raise ValueError(f'Missing, empty or incorrect-size download: {name}')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if asset.get('digest') and asset['digest'] != 'sha256:' + digest:
            raise ValueError(f'GitHub digest mismatch: {name}')
        files.append({'name': name, 'asset_id': asset['id'], 'size': asset['size'],
                      'sha256': digest, 'url': asset['browser_download_url']})
    return {'schema_version': 1, 'product': 'AuraPT', 'version': version,
            'repository': repo, 'release_id': data['id'], 'tag': data['tag_name'],
            'release_url': data['html_url'], 'published_at': data['published_at'],
            'programming_method': 'SEGGER standalone', 'files': files,
            'firmware_source_commit': None, 'hardware_profile': None,
            'engineering_approved': False}


def fingerprints(assets):
    return [{k: a.get(k) for k in ('id', 'name', 'size', 'digest', 'updated_at', 'state')}
            for a in assets]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
        parser.error('Expected owner/repository.')
    data = release(args.repo, args.tag)
    _, selected = select_assets(data)
    generated_names = ('production-manifest.json', 'SHA256SUMS.txt')
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        existing = {a['name']: a for a in data['assets']}
        for asset in selected:
            gh('release', 'download', args.tag, '--repo', args.repo,
               '--pattern', asset['name'], '--dir', str(folder))
        manifest = build_manifest(args.repo, data, folder)
        payloads = {
            'production-manifest.json': (json.dumps(manifest, indent=2) + '\n').encode(),
            'SHA256SUMS.txt': ''.join(f"{f['sha256']}  {f['name']}\n" for f in manifest['files']).encode(),
        }
        # Refuse a release whose inputs changed while hashing.
        fresh = release(args.repo, args.tag)
        _, latest_selected = select_assets(fresh)
        if fresh['id'] != data['id'] or fingerprints(latest_selected) != fingerprints(selected) or fresh['published_at'] != data['published_at']:
            raise ValueError('Release inputs changed during processing. Run again.')
        pending = []
        for name in generated_names:
            if name in existing:
                gh('release', 'download', args.tag, '--repo', args.repo,
                   '--pattern', name, '--dir', str(folder))
                if (folder / name).read_bytes() != payloads[name]:
                    raise ValueError('Existing metadata differs. Publish a new version; do not overwrite a pinned release.')
            else:
                (folder / name).write_bytes(payloads[name])
                pending.append(str(folder / name))
        if pending:
            gh('release', 'upload', args.tag, *pending, '--repo', args.repo)
        print(f"Verified {len(manifest['files'])} assets for {data['tag_name']}; metadata attached.")


if __name__ == '__main__':
    main()
