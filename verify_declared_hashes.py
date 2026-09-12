#!/usr/bin/env python3
"""Compare declared SHA-256 values with hashes recomputed from resolvable files.

Motivation: an operational incident on 2026-09-12 contained ten incorrect published
hashes that shared sixteen leading characters with the actual values. Prefix
agreement is consistent with reuse, but cannot prove a cause or previous validity.

Usage:
  python3 verify_declared_hashes.py doc1.md doc2.md  # inspect declarations
  python3 verify_declared_hashes.py --strict README.md  # exit 2 on mismatch
  python3 verify_declared_hashes.py --fetch-urls README.md  # explicit URL fallback

Recognizes lines starting with 64 lowercase hex characters, whitespace and a name.
Only a single filename adjacent to the document is supported; paths are unresolved.
Mismatch labels: fabricated for >=16 shared leading characters, stale otherwise.
These labels do not prove cause or provenance. --fetch-urls is fallback only when
local bytes cannot be read, not remote verification of an existing local copy.
HTTPS URL selection requires an exact once-decoded final path segment; distinct
matching URLs are unresolved. No download-size cap or overall retry time bound.
Do not fetch URLs in untrusted documents or private endpoints.
JSON: checked, defects (doc/file/declared/actual/prefix_match/verdict), unresolved,
fired and English advice. Exit: 0 by default; --strict exits 2 on a mismatch.
"""
import sys, os, re, json, hashlib, subprocess
from urllib.parse import urlsplit, unquote

HASH_LINE = re.compile(r'^([0-9a-f]{64})\s{1,4}(\S.*?)\s*$')
URL = re.compile(r'https://[^\s)\'"]+')

def _read_local(doc, name):
    p = os.path.join(os.path.dirname(os.path.abspath(doc)), name)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, 'rb') as stream:
            return stream.read()
    except OSError:
        return None

def _read_url(urls, name):
    cand = set()
    for url in urls:
        try:
            # Reject malformed escapes and control characters before parsing:
            # urlsplit can otherwise strip some of those characters silently.
            if re.search(r'[\x00-\x20\x7f]|%(?![0-9a-fA-F]{2})', url):
                continue
            parts = urlsplit(url)
            if parts.scheme != 'https' or not parts.hostname or parts.username is not None:
                continue
            _ = parts.port  # invalid port syntax raises ValueError
            filename = unquote(parts.path.rsplit('/', 1)[-1], errors='strict')
            if filename == name:
                # Fragments are not sent to the server; queries ARE significant.
                cand.add(parts._replace(fragment='').geturl())
        except (ValueError, UnicodeError):
            continue
    if len(cand) != 1:
        return None
    try:
        response = subprocess.run(['curl', '-sfL', '--proto', '=https', '--proto-redir', '=https',
                                   '--retry', '3', '--retry-all-errors', '--max-time', '300', next(iter(cand))],
                                  capture_output=True)
    except OSError:
        return None
    return response.stdout if response.returncode == 0 else None

def verify(docs, fetch_urls=False):
    defects, unresolved, checked = [], [], 0
    for doc in docs:
        try:
            with open(doc, encoding='utf-8', errors='ignore') as stream:
                text = stream.read()
        except OSError:
            continue
        urls = URL.findall(text) if fetch_urls else []
        for line in text.splitlines():
            m = HASH_LINE.match(line)
            if not m:
                continue
            declared, name = m.group(1), m.group(2).strip('`* ')
            if name != os.path.basename(name) or name in ('', '.', '..'):
                unresolved.append({'doc': doc, 'file': name, 'reason': 'unsupported_path'})
                continue
            data = _read_local(doc, name)
            if data is None and fetch_urls:
                data = _read_url(urls, name)
            if data is None:
                unresolved.append({'doc': doc, 'file': name})
                continue
            checked += 1
            actual = hashlib.sha256(data).hexdigest()
            if actual != declared:
                pref = len(os.path.commonprefix([declared, actual]))
                defects.append({'doc': doc, 'file': name, 'declared': declared, 'actual': actual,
                                'prefix_match': pref, 'verdict': 'fabricated' if pref >= 16 else 'stale'})
    return {'checked': checked, 'defects': defects, 'unresolved': unresolved}

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    strict = '--strict' in sys.argv
    res = verify(args, fetch_urls='--fetch-urls' in sys.argv)
    res['fired'] = bool(res['defects'])
    res['advice'] = ('The declared SHA-256 does not match the actual file. Verdict labels do not prove cause or provenance. '
                     'Before delivering or publishing, replace the declaration with a value recomputed from the actual file.') if res['fired'] else ''
    print(json.dumps(res, ensure_ascii=False))
    sys.exit(2 if (strict and res['fired']) else 0)
