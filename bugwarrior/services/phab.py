import logging
import typing

import phabricator
import pydantic.v1

from bugwarrior import config
from bugwarrior.services import Service, Issue

log = logging.getLogger(__name__)


class PhabricatorConfig(config.ServiceConfig):
    service: typing.Literal['phabricator']

    user_phids: config.ConfigList = config.ConfigList([])
    project_phids: config.ConfigList = config.ConfigList([])
    host: typing.Optional[pydantic.v1.AnyUrl]
    ignore_cc: typing.Optional[bool] = None
    ignore_author: typing.Optional[bool] = None
    ignore_owner: bool = False
    ignore_reviewers: bool = False

    # XXX Override common service configuration
    only_if_assigned: bool = False


class PhabricatorIssue(Issue):
    TITLE = 'phabricatortitle'
    URL = 'phabricatorurl'
    TYPE = 'phabricatortype'
    OBJECT_NAME = 'phabricatorid'

    UDAS = {
        TITLE: {
            'type': 'string',
            'label': 'Phabricator Title',
        },
        URL: {
            'type': 'string',
            'label': 'Phabricator URL',
        },
        TYPE: {
            'type': 'string',
            'label': 'Phabricator Type',
        },
        OBJECT_NAME: {
            'type': 'string',
            'label': 'Phabricator Object',
        },
    }
    UNIQUE_KEY = (URL, )

    PRIORITY_MAP = {
        'Needs Triage': None,
        'Unbreak Now!': 'H',
        'High': 'H',
        'Normal': 'M',
        'Low': 'L',
        'Wishlist': 'L',
    }

    def to_taskwarrior(self):
        return {
            'project': self.extra['project'],
            'priority': self.priority,
            'annotations': self.extra.get('annotations', []),

            self.URL: self.record['uri'],
            self.TYPE: self.extra['type'],
            self.TITLE: self.record['title'],
            self.OBJECT_NAME: self.record['uri'].split('/')[-1],
        }

    def get_default_description(self):
        return self.build_default_description(
            title=self.record['title'],
            url=self.record['uri'],
            number=self.record['uri'].split('/')[-1],
            cls=self.extra['type'],
        )

    @property
    def priority(self):
        return self.PRIORITY_MAP.get(self.record.get('priority')) \
            or self.config.default_priority


class PhabricatorService(Service):
    ISSUE_CLASS = PhabricatorIssue
    CONFIG_SCHEMA = PhabricatorConfig

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        # These read login credentials from ~/.arcrc
        if self.config.host:
            self.api = phabricator.Phabricator(host=self.config.host)
        else:
            self.api = phabricator.Phabricator()

        self.ignore_cc = (
            self.config.ignore_cc if self.config.ignore_cc is not None
            else self.config.only_if_assigned)
        self.ignore_author = (
            self.config.ignore_author if self.config.ignore_author is not None
            else self.config.only_if_assigned)

    def tasks(self):
        # If self.config.user_phids or self.config.project_phids is set,
        # retrict API calls to user_phids or project_phids to avoid time out
        # with Phabricator installations with huge userbase.
        try:
            if self.config.user_phids or self.config.project_phids:
                if self.config.user_phids:
                    tasks_owner = self.api.maniphest.query(
                        status='status-open',
                        ownerPHIDs=self.config.user_phids)
                    tasks_cc = self.api.maniphest.query(
                        status='status-open',
                        ccPHIDs=self.config.user_phids)
                    tasks_author = self.api.maniphest.query(
                        status='status-open',
                        authorPHIDs=self.config.user_phids)
                    tasks = list(tasks_owner.items()) + list(tasks_cc.items()) + \
                        list(tasks_author.items())
                    # Delete duplicates
                    seen = set()
                    tasks = [item for item in tasks if str(
                        item[1]) not in seen and not seen.add(str(item[1]))]
                if self.config.project_phids:
                    tasks = self.api.maniphest.query(
                        status='status-open',
                        projectPHIDs=self.config.project_phids)
                    tasks = tasks.items()
            else:
                tasks = self.api.maniphest.query(status='status-open')
                tasks = tasks.items()
        except phabricator.APIError as err:
            log.warn("Could not read tasks from Maniphest: %s" % err)
            return

        log.info("Found %i tasks" % len(tasks))

        for phid, task in tasks:

            project = self.config.target  # a sensible default

            this_task_matches = False

            if not self.config.user_phids and not self.config.project_phids:
                this_task_matches = True

            if self.config.user_phids:
                # Checking whether authorPHID, ccPHIDs, ownerPHID
                # are intersecting with self.config.user_phids
                task_relevant_to = set()
                if not self.ignore_cc:
                    task_relevant_to.update(task['ccPHIDs'])
                if not self.config.ignore_owner:
                    task_relevant_to.add(task['ownerPHID'])
                if not self.ignore_author:
                    task_relevant_to.add(task['authorPHID'])
                if len(task_relevant_to.intersection(
                        self.config.user_phids)) > 0:
                    this_task_matches = True

            if self.config.project_phids:
                # Checking whether projectPHIDs
                # is intersecting with self.config.project_phids
                task_relevant_to = set(task['projectPHIDs'])
                if len(task_relevant_to.intersection(
                        self.config.project_phids)) > 0:
                    this_task_matches = True

            if not this_task_matches:
                continue

            extra = {
                'project': project,
                'type': 'issue',
                # 'annotations': self.annotations(phid, issue)
            }

            yield self.get_issue_for_record(task, extra)

    def revisions(self):
        try:
            diffs = self.api.differential.query(status='status-open')
        except phabricator.APIError as err:
            log.warn("Could not read revisions from Differential: %s" % err)
            return

        diffs = list(diffs)

        log.info("Found %i differentials" % len(diffs))

        for diff in diffs:

            project = self.config.target  # a sensible default

            this_diff_matches = False

            if not self.config.user_phids and not self.config.project_phids:
                this_diff_matches = True

            if self.config.user_phids:
                # Checking whether authorPHID, ccPHIDs, reviewers
                # are intersecting with self.config.user_phids
                diff_relevant_to = set()
                if not self.config.ignore_reviewers:
                    diff_relevant_to.update(list(diff['reviewers']))
                if not self.ignore_cc:
                    diff_relevant_to.update(diff['ccs'])
                if not self.ignore_author:
                    diff_relevant_to.add(diff['authorPHID'])
                if len(diff_relevant_to.intersection(
                        self.config.user_phids)) > 0:
                    this_diff_matches = True

            if self.config.project_phids:
                # Checking whether projectPHIDs
                # is intersecting with self.config.project_phids
                phabricator_projects = []
                try:
                    phabricator_projects = diff['phabricator:projects']
                except KeyError:
                    pass

                diff_relevant_to = set(phabricator_projects + [diff['repositoryPHID']])
                if len(diff_relevant_to.intersection(
                        self.config.project_phids)) > 0:
                    this_diff_matches = True

            if not this_diff_matches:
                continue

            extra = {
                'project': project,
                'type': 'pull_request',
                # 'annotations': self.annotations(phid, issue)
            }
            yield self.get_issue_for_record(diff, extra)

    def issues(self):
        yield from self.tasks()
        yield from self.revisions()
