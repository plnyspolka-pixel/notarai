"""Choose the least intrusive authorized runtime for a kancelaria.

This is an advisory, deterministic planning stage. No network probes and no
resources are provisioned until a separately authorized workflow runs.
"""
from dataclasses import dataclass
from enum import Enum


class Runtime(str, Enum):
    REMOTE_API = 'remote_api'
    CLOUD_BROWSER = 'cloud_browser'
    HOSTED_WINDOWS_VM = 'hosted_windows_vm'
    ON_PREM_VM = 'on_prem_vm'
    LOCAL_CONNECTOR = 'local_connector'
    HUMAN_SETUP = 'human_setup'


@dataclass(frozen=True)
class Capabilities:
    # Booleans reflect VERIFIED capability + authorization, not vendor claims.
    authorized_remote_api: bool = False
    web_app: bool = False
    reachable_from_cloud: bool = False
    desktop_app: bool = False
    windows_vm_licensed: bool = False
    database_reachable_from_hosted_vm: bool = False
    on_prem_vm_available: bool = False
    narrow_connector_permitted: bool = False


@dataclass(frozen=True)
class Deployment:
    runtime: Runtime
    requires: tuple[str, ...]
    reason: str


def choose_runtime(c: Capabilities) -> Deployment:
    """First safe option wins; never pretend local-only data is reachable."""
    if c.authorized_remote_api and c.reachable_from_cloud:
        return Deployment(Runtime.REMOTE_API, (), 'verified_authorized_api')
    if c.web_app and c.reachable_from_cloud:
        return Deployment(Runtime.CLOUD_BROWSER, ('isolated_browser_profile',), 'web_ui')
    if c.desktop_app and c.windows_vm_licensed and c.database_reachable_from_hosted_vm:
        return Deployment(Runtime.HOSTED_WINDOWS_VM, ('dedicated_vm', 'robot_account'), 'windows_cloud')
    if c.desktop_app and c.on_prem_vm_available:
        return Deployment(Runtime.ON_PREM_VM, ('dedicated_vm', 'robot_account'), 'local_database')
    if c.narrow_connector_permitted:
        return Deployment(Runtime.LOCAL_CONNECTOR, ('explicit_admin_approval',), 'limited_local_connectivity')
    return Deployment(Runtime.HUMAN_SETUP, ('license_and_data_access_review',), 'no_safe_automatic_runtime')
