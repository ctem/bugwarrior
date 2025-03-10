import json
import typing

import requests

from bugwarrior import config
from bugwarrior.services import Service, Issue, Client


class GerritConfig(config.ServiceConfig):
    service: typing.Literal['gerrit']
    base_uri: config.StrippedTrailingSlashUrl
    username: str
    password: str

    ssl_ca_path: typing.Optional[config.ExpandedPath] = None
    query: str = 'is:open+is:reviewer'


class GerritIssue(Issue):
    SUMMARY = 'gerritsummary'
    URL = 'gerriturl'
    FOREIGN_ID = 'gerritid'
    BRANCH = 'gerritbranch'
    TOPIC = 'gerrittopic'
    STATUS = 'gerritstatus'
    WORK_IN_PROGRESS = 'gerritwip'

    UDAS = {
        SUMMARY: {
            'type': 'string',
            'label': 'Gerrit Summary'
        },
        URL: {
            'type': 'string',
            'label': 'Gerrit URL',
        },
        FOREIGN_ID: {
            'type': 'numeric',
            'label': 'Gerrit Change ID'
        },
        BRANCH: {
            'type': 'string',
            'label': 'Gerrit Branch',
        },
        TOPIC: {
            'type': 'string',
            'label': 'Gerrit Topic',
        },
        STATUS: {
            'type': 'string',
            'label': 'Gerrit Status',
        },
        WORK_IN_PROGRESS: {
            'type': 'numeric',
            'label': 'Gerrit Work in Progress',
        },
    }
    UNIQUE_KEY = (URL, )

    def to_taskwarrior(self):
        return {
            'project': self.record['project'],
            'annotations': self.extra['annotations'],
            self.URL: self.extra['url'],

            'priority': self.config.default_priority,
            'tags': [],
            self.FOREIGN_ID: self.record['_number'],
            self.SUMMARY: self.record['subject'],
            self.BRANCH: self.record['branch'],
            self.TOPIC: self.record.get('topic', 'notopic'),
            self.STATUS: self.record.get('status', ''),
            self.WORK_IN_PROGRESS: int(self.record.get('work_in_progress', 0)),
        }

    def get_default_description(self):
        return self.build_default_description(
            title=self.record['subject'],
            url=self.extra['url'],
            number=self.record['_number'],
            cls='pull_request',
        )


class GerritService(Service, Client):
    ISSUE_CLASS = GerritIssue
    CONFIG_SCHEMA = GerritConfig

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.password = self.get_password('password', self.config.username)
        self.session = requests.session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
        })
        self.query_string = (
            self.config.query + '&o=MESSAGES&o=DETAILED_ACCOUNTS')

        if self.config.ssl_ca_path:
            self.session.verify = self.config.ssl_ca_path

        # uses digest authentication if supported by the server, fallback to basic
        # gerrithub.io supports only basic
        response = self.session.head(self.config.base_uri + '/a/')
        if 'digest' in response.headers.get('www-authenticate', '').lower():
            self.session.auth = requests.auth.HTTPDigestAuth(
                self.config.username, self.password)
        else:
            self.session.auth = requests.auth.HTTPBasicAuth(
                self.config.username, self.password)

    @staticmethod
    def get_keyring_service(config):
        return f"gerrit://{config.base_uri}"

    def issues(self):
        # Construct the whole url by hand here, because otherwise requests will
        # percent-encode the ':' characters, which gerrit doesn't like.
        url = self.config.base_uri + '/a/changes/?q=' + self.query_string
        response = self.session.get(url)
        response.raise_for_status()
        # The response has some ")]}'" garbage prefixed.
        body = response.text[4:]
        changes = json.loads(body)

        for change in changes:
            extra = {
                'url': self.build_url(change),
                'annotations': self.annotations(change),
            }
            yield self.get_issue_for_record(change, extra)

    def build_url(self, change):
        return '%s/#/c/%i/' % (self.config.base_uri, change['_number'])

    def annotations(self, change):
        entries = []
        for item in change['messages']:
            for key in ['name', 'username', 'email']:
                if key in item['author']:
                    username = item['author'][key]
                    break
            else:
                username = item['author']['_account_id']
            # Gerrit messages are really messy
            message = item['message']\
                .lstrip('Patch Set ')\
                .lstrip("%s:" % item['_revision_number'])\
                .strip()\
                .replace('\n', ' ')
            entries.append((username, message,))

        return self.build_annotations(entries, self.build_url(change))
