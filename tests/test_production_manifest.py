import copy
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('manifest', Path(__file__).parents[1] / 'scripts/production_manifest.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    return {'id': 123, 'tag_name': 'v3.4', 'draft': False, 'prerelease': False,
            'html_url': 'https://github.com/MineARC/aura-pt-release/releases/tag/v3.4',
            'published_at': '2026-11-09T00:00:00Z',
            'assets': [{'id': i, 'name': name, 'size': 3, 'state': 'uploaded',
                        'browser_download_url': 'https://example.test/' + name}
                       for i, name in enumerate(['apt-3-4.dat', 'pt.cfg'], 1)]}


class ManifestTests(unittest.TestCase):
    def test_hash_actual_bytes_and_keep_unknown_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ('apt-3-4.dat', 'pt.cfg'):
                (folder / name).write_bytes(b'abc')
            result = m.build_manifest('MineARC/aura-pt-release', fixture(), folder)
            self.assertEqual(result['files'][0]['sha256'], hashlib.sha256(b'abc').hexdigest())
            self.assertIsNone(result['firmware_source_commit'])
            self.assertFalse(result['engineering_approved'])

    def test_missing_dat_and_cfg(self):
        for index in (0, 1):
            data = fixture()
            data['assets'].pop(index)
            with self.assertRaises(ValueError):
                m.select_assets(data)

    def test_version_is_not_decimal(self):
        data = fixture()
        data['tag_name'] = 'v3.10'
        data['assets'][0]['name'] = 'apt-3-10.dat'
        self.assertEqual(m.select_assets(data)[0], '3.10')

    def test_exclude_drafts_and_prereleases(self):
        for key in ('draft', 'prerelease'):
            data = fixture()
            data[key] = True
            with self.assertRaises(ValueError):
                m.select_assets(data)

    def test_digest_and_size_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ('apt-3-4.dat', 'pt.cfg'):
                (folder / name).write_bytes(b'abc')
            for update in ({'size': 5}, {'digest': 'sha256:' + '0' * 64}):
                data = fixture()
                data['assets'][0].update(update)
                with self.assertRaises(ValueError):
                    m.build_manifest('MineARC/aura-pt-release', data, folder)

    def test_download_counts_do_not_invalidate_snapshot(self):
        data = fixture()['assets']
        changed = copy.deepcopy(data)
        changed[0]['download_count'] = 42
        self.assertEqual(m.fingerprints(data), m.fingerprints(changed))
        changed[0]['id'] = 99
        self.assertNotEqual(m.fingerprints(data), m.fingerprints(changed))

    def test_end_to_end_idempotence_and_refuse_replacement(self):
        data = fixture()
        remote = {'apt-3-4.dat': b'abc', 'pt.cfg': b'abc'}

        def fake_gh(*args):
            if args[:2] == ('release', 'download'):
                name = args[args.index('--pattern') + 1]
                (Path(args[args.index('--dir') + 1]) / name).write_bytes(remote[name])
            elif args[:2] == ('release', 'upload'):
                for name in args[3:args.index('--repo')]:
                    path = Path(name)
                    remote[path.name] = path.read_bytes()
                    data['assets'].append({'name': path.name})
            return ''

        with patch.object(m, 'release', side_effect=lambda *a: copy.deepcopy(data)), \
             patch.object(m, 'gh', side_effect=fake_gh), \
             patch('sys.argv', ['manifest', '--repo', 'MineARC/aura-pt-release', '--tag', 'v3.4']):
            m.main()
            first = remote['production-manifest.json']
            m.main()
            self.assertEqual(first, remote['production-manifest.json'])
            remote['apt-3-4.dat'] = b'xyz'
            with self.assertRaises(ValueError):
                m.main()


if __name__ == '__main__':
    unittest.main()
