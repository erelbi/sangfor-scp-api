# -*- coding: utf-8 -*-
# Sangfor SCP API Library
# This library is used to interact with the Open-API of Sangfor HCI and SCP platforms.
# It uses an EC2-like signing method for authentication.

import requests
import datetime
import hashlib
import hmac
import json
import urllib3
from urllib.parse import urlparse
import sys

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Library Helper Functions ---
def _sign(key, message):
    """Private function to sign a message using HMAC-SHA256."""
    return hmac.new(key, message.encode('utf-8'), hashlib.sha256).digest()

def _get_signature_key(key, date_stamp, region_name, service_name):
    """Private function to generate the signature key required for authentication."""
    k_date = _sign(("AWS4" + key).encode('utf-8'), date_stamp)
    k_region = _sign(k_date, region_name)
    k_service = _sign(k_region, service_name)
    k_signing = _sign(k_service, "aws4_request")
    return k_signing

class _EC2RequestAuth(requests.auth.AuthBase):
    """
    A private helper class that generates AWS Signature V4-like authentication headers
    for each request.
    """
    def __init__(self, access_key, secret_key, region, service):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.service = service
        self.algorithm = 'AWS4-HMAC-SHA256'

    def __call__(self, r):
        t = datetime.datetime.now(datetime.UTC)
        amzdate = t.strftime('%Y%m%dT%H%M%SZ')
        datestamp = t.strftime('%Ym%d')

        url = urlparse(r.url)
        host = url.netloc

        headers = r.headers.copy()
        headers['X-Amz-Date'] = amzdate
        headers['Host'] = host

        canonical_uri = url.path if url.path else '/'
        canonical_querystring = "" # This is kept empty due to API's non-standard signature verification.
        
        signed_headers_list = sorted(['host', 'x-amz-date'])
        signed_headers_str = ';'.join(signed_headers_list)
        
        canonical_headers = ''.join([f"{header}:{headers[header]}\n" for header in signed_headers_list])
        
        body = r.body or b''
        body_hash = hashlib.sha256(body if isinstance(body, bytes) else body.encode('utf-8')).hexdigest()

        canonical_request = '\n'.join([
            r.method, canonical_uri, canonical_querystring,
            canonical_headers, signed_headers_str, body_hash
        ])

        credential_scope = f"{datestamp}/{self.region}/{self.service}/aws4_request"
        string_to_sign = '\n'.join([
            self.algorithm, amzdate, credential_scope,
            hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        ])

        signing_key = _get_signature_key(self.secret_key, datestamp, self.region, self.service)
        signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        authorization_header = (
            f"{self.algorithm} Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers_str}, Signature={signature}"
        )
        headers['Authorization'] = authorization_header
        
        r.headers = headers
        return r

class SangforSDKClient:
    """
    The main client class for interacting with the Sangfor Cloud Platform Open-API.
    """
    def __init__(self, access_key, secret_key, region, service, base_url, verbose=False):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.service = service
        self.base_url = base_url.rstrip('/')
        self.verbose = verbose
        self.session = requests.Session()
        self.session.auth = _EC2RequestAuth(
            access_key=self.access_key,
            secret_key=self.secret_key,
            region=self.region,
            service=self.service
        )
        self._all_vms_cache = None # Cache for name-based searches

    def send_request(self, method, path, params=None, json_data=None):
        """Sends an authenticated request to the specified API endpoint."""
        full_url = f"{self.base_url}{path}"
        try:
            if self.verbose:
                print(f"==> Request: {method} {full_url} (Params: {params})", file=sys.stderr)
            
            response = self.session.request(
                method=method, url=full_url, params=params,
                json=json_data, verify=False
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if self.verbose:
                print(f"==> API Error: {e.response.status_code} {e.response.reason}", file=sys.stderr)
                print(f"==> Server Response: {e.response.text}", file=sys.stderr)
            return e.response.json()
        except requests.exceptions.RequestException as e:
            print(f"==> Connection Error: {e}", file=sys.stderr)
            return None
        except json.JSONDecodeError:
            print(f"==> Invalid JSON response from API: {response.text}", file=sys.stderr)
            return None

    def get_availability_zones(self):
        """Queries all available resource pools (availability zones)."""
        path = '/janus/20190725/azs'
        return self.send_request('GET', path)

    def get_vms(self, page_num=None, page_size=None):
        """Queries a paginated list of VMs."""
        path = '/janus/20190725/servers'
        params = {}
        if page_num is not None:
            params['page_num'] = page_num
        if page_size:
            params['page_size'] = page_size
        return self.send_request('GET', path, params=params)

    def get_all_vms(self, use_cache=True):
        """
        Fetches all VMs by handling pagination and returns them as a single list.
        """
        if use_cache and self._all_vms_cache is not None:
            if self.verbose: print("  - Using cached VM list.", file=sys.stderr)
            return self._all_vms_cache
        
        all_vms = []
        current_page = 0
        PAGE_SIZE = 100
        while True:
            if self.verbose:
                sys.stderr.write(f"\r  - Downloading VM list: Page {current_page}...")
                sys.stderr.flush()
            response = self.get_vms(page_num=current_page, page_size=PAGE_SIZE)
            if not (response and response.get('data') and isinstance(response['data'].get('data'), list)):
                break
            vms_on_this_page = response['data']['data']
            all_vms.extend(vms_on_this_page)
            next_page_info = response['data'].get('next_page_num')
            if not next_page_info or not vms_on_this_page:
                break
            current_page = int(next_page_info)
        
        if self.verbose:
            sys.stderr.write("\r" + " " * 50 + "\r")
        
        self._all_vms_cache = all_vms
        return all_vms

    def get_vm_details(self, vm_id):
        """Queries the detailed information for a specific VM by its ID."""
        if not vm_id: raise ValueError("A vm_id is required.")
        path = f'/janus/20190725/servers/{vm_id}'
        return self.send_request('GET', path)

    def find_vm(self, identifier):
        """
        Finds a VM by its ID or exact name and returns its detailed information.
        """
        is_uuid = len(identifier.split('-')) == 5
        
        if is_uuid:
            if self.verbose: print("Input detected as an ID. Querying directly...", file=sys.stderr)
            return self.get_vm_details(identifier)
        else:
            if self.verbose: print("Input detected as a name. Scanning full VM list...", file=sys.stderr)
            vm_list = self.get_all_vms()
            target_vm = next((vm for vm in vm_list if vm.get('name') == identifier), None)
            if target_vm:
                vm_id = target_vm.get('id')
                if self.verbose: print(f"Found '{identifier}'. Fetching details (ID: {vm_id})...", file=sys.stderr)
                return self.get_vm_details(vm_id)
            else:
                if self.verbose: print(f"No virtual machine found with the name '{identifier}'.", file=sys.stderr)
                return None
        return None

    def get_vm_snapshots(self, vm_id):
        """Queries all snapshots for a specific VM."""
        if not vm_id: raise ValueError("A vm_id is required.")
        path = f'/janus/20190725/servers/{vm_id}/snapshots'
        return self.send_request('GET', path)
    
    def get_vm_backups(self, vm_id):
        """Queries all backups for a specific VM."""
        if not vm_id: raise ValueError("A vm_id is required.")
        path = f'/janus/20190725/servers/{vm_id}/backups'
        return self.send_request('GET', path)

    def generate_infrastructure_report(self):
        """
        Scans the entire infrastructure and generates a general resource utilization report.
        """
        if self.verbose:
            print("Generating infrastructure report. Scanning all virtual machines...", file=sys.stderr)
        
        all_vms = self.get_all_vms(use_cache=False)
        az_response = self.get_availability_zones()
        az_list = az_response.get('data', {}).get('data', []) if az_response else []

        if not all_vms:
            return {"error": "No virtual machines were found."}

        report = {
            "report_generated_at": datetime.datetime.now().isoformat(),
            "overall_totals": {
                "total_vms": 0,
                "vms_by_status": {"running": 0, "stopped": 0, "other": 0},
                "total_provisioned": {"cpu_cores": 0, "memory_gb": 0.0, "disk_tb": 0.0},
                "total_used": {"cpu_mhz": 0.0, "memory_gb": 0.0, "disk_gb": 0.0}
            },
            "by_availability_zone": {}
        }

        if az_list:
            for az in az_list:
                az_name = az.get('name')
                if az_name:
                    report['by_availability_zone'][az_name] = {
                        "total_vms": 0,
                        "vms_by_status": {"running": 0, "stopped": 0, "other": 0},
                        "total_provisioned": {"cpu_cores": 0, "ram_gb": 0.0, "disk_tb": 0.0},
                        "total_used": {"cpu_mhz": 0.0, "ram_gb": 0.0, "disk_gb": 0.0}
                    }
        
        for vm in all_vms:
            az_name = vm.get('az_name')
            if not az_name or az_name not in report['by_availability_zone']:
                continue

            status = vm.get('status', 'other')
            if status not in ['running', 'stopped']:
                status = 'other'

            # --- Calculate Overall Totals ---
            report['overall_totals']['total_vms'] += 1
            report['overall_totals']['vms_by_status'][status] += 1
            
            cores = vm.get('cores', 0)
            memory_mb = vm.get('memory_mb', 0.0)
            total_disk_mb = sum(disk.get('size_mb', 0.0) for disk in vm.get('disks', []))

            report['overall_totals']['total_provisioned']['cpu_cores'] += cores
            report['overall_totals']['total_provisioned']['memory_gb'] += memory_mb / 1024
            report['overall_totals']['total_provisioned']['disk_tb'] += total_disk_mb / (1024 * 1024)
            
            # --- Calculate AZ-Specific Totals ---
            az_report = report['by_availability_zone'][az_name]
            az_report['total_vms'] += 1
            az_report['vms_by_status'][status] += 1
            az_report['total_provisioned']['cpu_cores'] += cores
            az_report['total_provisioned']['ram_gb'] += memory_mb / 1024
            az_report['total_provisioned']['disk_tb'] += total_disk_mb / (1024 * 1024)

            # --- Calculate Used Resources ---
            if vm.get('cpu_status'):
                used_mhz = vm['cpu_status'].get('used_mhz', 0.0)
                report['overall_totals']['total_used']['cpu_mhz'] += used_mhz
                az_report['total_used']['cpu_mhz'] += used_mhz

            if vm.get('memory_status'):
                used_mem_mb = vm['memory_status'].get('used_mb', 0.0)
                report['overall_totals']['total_used']['memory_gb'] += used_mem_mb / 1024
                az_report['total_used']['ram_gb'] += used_mem_mb / 1024

            if vm.get('storage_status'):
                used_disk_mb = vm['storage_status'].get('used_mb', 0.0)
                report['overall_totals']['total_used']['disk_gb'] += used_disk_mb / 1024
                az_report['total_used']['disk_gb'] += used_disk_mb / 1024
        
        # --- Finalize Report (Rounding) ---
        for category in [report['overall_totals']] + list(report['by_availability_zone'].values()):
            for section in ['total_provisioned', 'total_used']:
                for key, value in category[section].items():
                    category[section][key] = round(value, 2)
        
        return report
