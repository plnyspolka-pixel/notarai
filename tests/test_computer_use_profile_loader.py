import hashlib
import hmac
import json

import pytest

from computer_use.profile_loader import ProfileRejected, load_verified_profile

KEY = b'a' * 32


def signed_profile(tenant='kancelaria_A', extra_fields=None):
    profile = {'tenant_id':tenant, 'revision':1, 'app':{
        'app_id':'generic_program', 'start_url':'https://internal.example.test/',
        'windows_app':'notepad', 'fields': {
            'case_number':[{'kind':'css','selector':'#case_number'},
                           {'kind':'uia','selector':'CaseNumberField'}],
            **(extra_fields or {}),
        }
    }}
    raw = json.dumps(profile, sort_keys=True).encode()
    sig = hmac.new(KEY, raw, hashlib.sha256).hexdigest()
    return raw, sig


def test_signed_profile_is_loaded_without_per_vendor_code():
    raw, sig = signed_profile()
    verified = load_verified_profile(raw, sig, KEY, tenant_id='kancelaria_A')
    assert verified.revision == 1
    assert verified.app.field('case_number', kind='browser').selector == '#case_number'
    assert verified.app.field('case_number', kind='uia').selector == 'CaseNumberField'


def test_tampering_rejected():
    raw, sig = signed_profile()
    with pytest.raises(ProfileRejected, match='signature_mismatch'):
        load_verified_profile(raw.replace(b'#case_number', b'#other_field'), sig, KEY, tenant_id='kancelaria_A')


def test_tenant_binding_rejected():
    raw, sig = signed_profile('kancelaria_A')
    with pytest.raises(ProfileRejected, match='tenant_mismatch'):
        load_verified_profile(raw, sig, KEY, tenant_id='kancelaria_B')


def test_reject_untrusted_http_and_auto_draft():
    raw, sig = signed_profile(extra_fields={'hidden': {'kind':'css','selector':'input[name=password]',
                                                    'allow_draft_fill':False}})
    verified = load_verified_profile(raw, sig, KEY, tenant_id='kancelaria_A')
    assert verified.app.field('hidden', kind='browser').allow_draft_fill is False


def test_reject_oversized_profile():
    with pytest.raises(ProfileRejected):
        load_verified_profile(b' '*40000, '0'*64, KEY, tenant_id='kancelaria_A')


def test_wrong_key_rejected():
    raw, sig = signed_profile()
    with pytest.raises(ProfileRejected):
        load_verified_profile(raw, sig, b'b'*32, tenant_id='kancelaria_A')
