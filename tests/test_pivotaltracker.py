import datetime

from dateutil.tz import tzutc
import responses

from bugwarrior.collect import TaskConstructor
from bugwarrior.services.pivotaltracker import PivotalTrackerService

from .base import ServiceTest, AbstractServiceTest, ConfigTest

PROJECT = {
    'account_id': 100,
    'atom_enabled': True,
    'automatic_planning': True,
    'bugs_and_chores_are_estimatable': False,
    'created_at': '2019-05-14T12:00:05Z',
    'current_iteration_number': 15,
    'description': 'Expeditionary Battle Planetoid',
    'enable_following': True,
    'enable_incoming_emails': True,
    'enable_tasks': True,
    'has_google_domain': False,
    'id': 99,
    'initial_velocity': 10,
    'iteration_length': 1,
    'kind': 'project',
    'name': 'Death Star',
    'number_of_done_iterations_to_show': 4,
    'point_scale': '0,1,2,3',
    'point_scale_is_custom': False,
    'profile_content': """
This is a machine of war such as the universe has never known.
It's colossal, the size of a class-four moon.
And it possesses firepower unequaled in the history of warfare.
    """,
    'project_type': 'private',
    'public': False,
    'start_date': '2019-01-28',
    'start_time': '2019-05-14T12:00:10Z',
    'time_zone': {
        'kind': 'time_zone',
        'olson_name': 'America/Los_Angeles',
        'offset': '-07:00'},
    'updated_at': '2019-05-14T12:00:10Z',
    'velocity_averaged_over': 3,
    'version': 66,
    'week_start_day': 'Monday'}

STORY = {
    'project': PROJECT,
    'kind': 'story',
    'id': 561,
    'created_at': '2019-05-14T12:00:00Z',
    'updated_at': '2019-05-14T12:00:00Z',
    'accepted_at': '2019-05-14T12:00:00Z',
    'story_type': 'story',
    'estimate': 3,
    'name': 'Tractor beam loses power intermittently',
    'description': 'All your base are belong to us',
    'current_state': 'unstarted',
    'requested_by_id': 106,
    'url': 'http://localhost/story/show/561',
    'project_id': 99,
    'owner_ids':
    [
        106
    ],
    'labels':
    [
        {
            'kind': 'label',
            'id': 5101,
            'project_id': 99,
            'name': 'look sir metal',
            'created_at': '2019-05-14T12:00:05Z',
            'updated_at': '2019-05-14T12:00:05Z'
        },
    ]
}

USER = [
    {
        'created_at': '2019-05-14T12:00:00Z',
        'favorite': False,
        'id': 16200,
        'kind': 'project_membership',
        'person':
        {
            'kind': 'person',
            'id': 106,
            'name': 'Galen Marek',
            'email': 'marek@sith.mil',
            'initials': 'GM',
            'username': 'starkiller'
        },
        'project_color': 'b800bb',
        'project_id': 99,
        'role': 'member',
        'updated_at': '2019-05-14T12:00:00Z',
        'wants_comment_notification_emails': True,
        'will_receive_mention_notifications_or_emails': True
    }
]

TASKS = [
    {
        'kind': 'task',
        'id': 5,
        'story_id': 561,
        'description': 'Port 0',
        'complete': False,
        'position': 1,
        'created_at': '2019-05-14T12:00:00Z',
        'updated_at': '2019-05-14T12:00:00Z'
    },
    {
        'kind': 'task',
        'id': 6,
        'story_id': 561,
        'description': 'Port 90',
        'complete': False,
        'position': 2,
        'created_at': '2019-05-14T12:00:00Z',
        'updated_at': '2019-05-14T12:00:00Z'
    }
]

BLOCKERS = [
    {
        'kind': 'blocker',
        'id': 1100,
        'story_id': 561,
        'person_id': 106,
        'description': 'Set weapons to stun',
        'resolved': False,
        'created_at': '2019-05-14T12:00:00Z',
        'updated_at': '2019-05-14T12:00:00Z'
    }
]

QUERY = {
    "epics":
    {
        "epics":
        [
        ],
        "total_hits": 0
    },
    "query": "mywork:106",
    "stories": {
        "stories":
        [
            STORY
        ],
        "total_points": 0,
        "total_points_completed": 0,
        "total_hits": 1,
        "total_hits_with_done": 0
    }
}

EXTRA = {
    'request_user':
    [
        'request_user'
    ],
    'owned_user':
    [
        'owned_user'
    ],
    'annotations': TASKS,
    'blockers': BLOCKERS,
    'project_name': PROJECT['name']
}


class TestPivotalTrackerServiceConfig(ConfigTest):

    def setUp(self):
        super().setUp()
        self.config = {
            'general': {'targets': ['pivotal']},
            'pivotal': {'service': 'pivotaltracker'},
        }

    def test_validate_config(self):
        self.config['pivotal'].update({
            'account_ids': '12345',
            'user_id': '12345',
            'token': '12345',
        })

        self.validate()

    def test_validate_config_no_account_ids(self):
        self.config['pivotal'].update({
            'token': '123',
            'user_id': '12345',
        })

        self.assertValidationError(
            '[pivotal]\naccount_ids  <- field required')

    def test_validate_config_no_user_id(self):
        self.config['pivotal'].update({
            'account_ids': '12345',
            'token': '123',
        })

        self.assertValidationError(
            '[pivotal]\nuser_id  <- field required')

    def test_validate_config_token(self):
        self.config['pivotal'].update({
            'account_ids': '12345',
            'user_id': '12345',
        })

        self.assertValidationError(
            '[pivotal]\ntoken  <- field required')

    def test_validate_config_invalid_endpoint(self):
        self.config['pivotal'].update({
            'account_ids': '12345',
            'token': '123',
            'user_id': '12345',
            'version': 'v1',
        })

        self.assertValidationError(
            '[pivotal]\nversion  <- unexpected value')


class TestPivotalTrackerIssue(AbstractServiceTest, ServiceTest):
    SERVICE_CONFIG = {
        'service': 'pivotaltracker',
        'token': '123456',
        'user_id': 106,
        'account_ids': '100',
        'import_labels_as_tags': True,
        'import_blockers': True
    }

    def setUp(self):
        super().setUp()
        self.service = self.get_mock_service(PivotalTrackerService)
        responses.add(responses.GET,
                      'https://www.pivotaltracker.com/services/v5/projects?account_ids=100',
                      json=[PROJECT])
        responses.add(
            responses.GET,
            'https://www.pivotaltracker.com/services/v5/projects/99/search?query=mywork:106',
            json=QUERY)
        responses.add(responses.GET,
                      'https://www.pivotaltracker.com/services/v5/projects/99/stories/561/tasks',
                      json=TASKS)
        responses.add(responses.GET,
                      'https://www.pivotaltracker.com/services/v5/projects/99/stories/561/blockers',
                      json=BLOCKERS)
        responses.add(responses.GET,
                      'https://www.pivotaltracker.com/services/v5/projects/99/memberships',
                      json=USER)

    def test_to_taskwarrior(self):
        story = self.service.get_issue_for_record(
            STORY, EXTRA
        )

        expected_output = {
            'annotations':
            [
                {
                    'complete': False,
                    'created_at': '2019-05-14T12:00:00Z',
                    'description': 'Port 0',
                    'id': 5,
                    'kind': 'task',
                    'position': 1,
                    'story_id': 561,
                    'updated_at': '2019-05-14T12:00:00Z'
                },
                {
                    'complete': False,
                    'created_at': '2019-05-14T12:00:00Z',
                    'description': 'Port 90',
                    'id': 6,
                    'kind': 'task',
                    'position': 2,
                    'story_id': 561,
                    'updated_at': '2019-05-14T12:00:00Z'
                }
            ],
            'pivotalclosed': datetime.datetime(2019, 5, 14, 12, 0, tzinfo=tzutc()),
            'pivotalcreated': datetime.datetime(2019, 5, 14, 12, 0, tzinfo=tzutc()),
            'pivotalupdated': datetime.datetime(2019, 5, 14, 12, 0, tzinfo=tzutc()),
            'pivotalurl': 'http://localhost/story/show/561',
            'pivotalblockers':
            [
                {
                    'created_at': '2019-05-14T12:00:00Z',
                    'description': 'Set weapons to stun',
                    'id': 1100,
                    'kind': 'blocker',
                    'person_id': 106,
                    'resolved': False,
                    'story_id': 561,
                    'updated_at': '2019-05-14T12:00:00Z'
                }
            ],
            'pivotaldescription': 'All your base are belong to us',
            'pivotalestimate': 3,
            'pivotalid': 561,
            'pivotalowners': ['owned_user'],
            'pivotalprojectid': 99,
            'pivotalprojectname': 'Death Star',
            'pivotalrequesters': ['request_user'],
            'pivotalstorytype': 'story',
            'priority': 'M',
            'project': 'death_star',
            'tags':
            [
                'look_sir_metal'
            ]
        }
        actual_output = story.to_taskwarrior()
        self.assertEqual(actual_output, expected_output)

    @responses.activate
    def test_issues(self):
        story = next(self.service.issues())
        story_date = datetime.datetime(2019, 5, 14, 12, 0, tzinfo=tzutc())
        expected = {
            'annotations':
            [
                '@task - status: False - Port 0',
                '@task - status: False - Port 90'
            ],
            'description': (
                '(bw)Story#561 - Tractor beam loses power intermittently .. '
                'http://localhost/story/show/561'),
            'pivotalclosed': story_date,
            'pivotalcreated': story_date,
            'pivotalupdated': story_date,
            'pivotalurl': 'http://localhost/story/show/561',
            'pivotalblockers': 'Description: Set weapons to stun State: False',
            'pivotaldescription': 'All your base are belong to us',
            'pivotalestimate': 3,
            'pivotalid': 561,
            'pivotalowners': 'starkiller',
            'pivotalprojectid': 99,
            'pivotalprojectname': 'Death Star',
            'pivotalrequesters': 'starkiller',
            'pivotalstorytype': 'story',
            'priority': 'M',
            'project': 'death_star',
            'tags': ['look_sir_metal']
        }
        self.assertEqual(TaskConstructor(story).get_taskwarrior_record(), expected)
