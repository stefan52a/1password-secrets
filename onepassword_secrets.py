import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from io import StringIO
from tempfile import NamedTemporaryFile

from dotenv import dotenv_values
from sgqlc.endpoint.http import HTTPEndpoint

FLY_GRAPHQL_ENDPOINT = 'https://api.fly.io/graphql'
DATE_FORMAT = '%Y/%m/%d %H:%M:%S'
DEFAULT_ENV_FILE_NAME = '.env'


def get_1password_env_file_item_id(title_substring):
    secure_notes = json.loads(
        subprocess.check_output(
            ['op', 'item', 'list', '--categories',
                'Secure Note', '--format', 'json']
        )
    )

    item_id = next(
        (
            item['id']
            for item in secure_notes
            if title_substring in item['title']
        ),
        None
    )

    if item_id is None:
        raise_error(
            f'There is no secure note in 1password with a name containing `{title_substring}`'
        )

    return item_id


def get_item_from_1password(item_id):
    return json.loads(
        subprocess.check_output(
            ['op', 'item', 'get', item_id, '--format', 'json']
        )
    )


def get_envs_from_1password(item_id):
    item = get_item_from_1password(item_id)

    result = first(
        field.get('value')
        for field in item['fields']
        if field['id'] == 'notesPlain'
    )
    if result is None or result == "":
        raise_error("Empty secrets, aborting")

    return result


def get_filename_from_1password(item_id):
    item = get_item_from_1password(item_id)

    result = first(
        field.get('value')
        for field in item['fields']
        if field['label'] == 'file_name'
    )

    return result


def get_fly_auth_token():
    return json.loads(
        subprocess.check_output(['fly', 'auth', 'token', '--json'])
    )['token']


def update_fly_secrets(app_id, secrets):
    set_secrets_mutation = """
    mutation(
        $appId: ID!
        $secrets: [SecretInput!]!
        $replaceAll: Boolean!
    ) {
        setSecrets(
            input: {
                appId: $appId
                replaceAll: $replaceAll
                secrets: $secrets
            }
        ) {
            app {
                name
            }
            release {
                version
            }
        }
    }
    """

    secrets_input = [
        {'key':  key, 'value': value}
        for key, value in secrets.items()
    ]
    variables = {
        'appId': app_id,
        'secrets': secrets_input,
        'replaceAll': True
    }

    headers = {'Authorization': f'Bearer {get_fly_auth_token()}'}

    endpoint = HTTPEndpoint(
        FLY_GRAPHQL_ENDPOINT,
        headers
    )

    response = endpoint(
        query=set_secrets_mutation,
        variables=variables
    )

    if response.get('errors') is not None:
        raise_error(response['errors'][0])

    print(
        'Releasing fly app {} version {}'.format(
            app_id,
            response["data"]["setSecrets"]["release"]["version"]
        )
    )


def update_1password_secrets(item_id, content):
    subprocess.check_output([
        'op',
        'item',
        'edit',
        item_id,
        f'notesPlain={content}'
    ])


def update_1password_custom_field(item_id, field, value):
    subprocess.check_output([
        'op',
        'item',
        'edit',
        item_id,
        f'Generated by 1password-secrets.{field}[text]={value}',
        '--format',
        'json'
    ])


def get_secrets_from_envs(input: str):
    return dotenv_values(stream=StringIO(input))


def import_1password_secrets_to_fly(app_id):
    item_id = get_1password_env_file_item_id(f'fly:{app_id}')

    secrets = get_secrets_from_envs(get_envs_from_1password(item_id))

    update_fly_secrets(app_id, secrets)

    now_formatted = datetime.now().strftime(DATE_FORMAT)
    update_1password_custom_field(
        item_id,
        'last imported at',
        now_formatted
    )


def edit_1password_secrets(app_id):
    item_id = get_1password_env_file_item_id(f'fly:{app_id}')

    secrets = get_envs_from_1password(item_id)

    with NamedTemporaryFile('w+') as file:
        file.writelines(secrets)
        file.flush()
        subprocess.check_output(['code', '--wait', file.name])

        file.seek(0)
        output = file.read()

    if secrets == output:
        print("No changes detected, aborting.")
        return

    update_1password_secrets(item_id, output)

    now_formatted = datetime.now().strftime(DATE_FORMAT)
    update_1password_custom_field(
        item_id,
        'last edited at',
        now_formatted
    )

    user_input = ""
    while user_input.lower() not in ['y', 'n']:
        user_input = input(
            'Secrets updated in 1password, '
            f'do you wish to import secrets to the fly app {app_id} (y/n)?\n'
        )

    if user_input.lower() == 'y':
        import_1password_secrets_to_fly(app_id)


def get_local_secrets():
    repository = get_git_repository_name_from_current_directory()
    item_id = get_1password_env_file_item_id(f'repo:{repository}')

    secrets = get_envs_from_1password(item_id)

    env_file_name = get_filename_from_1password(item_id) or DEFAULT_ENV_FILE_NAME

    with open(env_file_name, 'w') as file:
        file.writelines(secrets)

    print(f'Successfully updated {env_file_name} from 1password')


def push_local_secrets():
    repository_name = get_git_repository_name_from_current_directory()
    item_id = get_1password_env_file_item_id(f'repo:{repository_name}')

    env_file_name = get_filename_from_1password(item_id) or DEFAULT_ENV_FILE_NAME

    with open(env_file_name, 'r') as file:
        secrets = file.read()

    update_1password_secrets(item_id, secrets)

    now_formatted = datetime.now().strftime(DATE_FORMAT)
    update_1password_custom_field(
        item_id,
        'last edited at',
        now_formatted
    )

    print(f'Successfully pushed secrets from {env_file_name} to 1password')


def get_git_repository_name_from_current_directory():
    GIT_REPOSITORY_REGEX = r"^(https|git)(:\/\/|@)([^\/:]+)[\/:]([^\/:]+)\/(.+).git$"

    try:
        git_remote_origin_url = subprocess.check_output([
            'git',
            'config',
            '--get',
            'remote.origin.url'
        ]).decode("utf-8")
    except subprocess.CalledProcessError:
        raise_error('Either not in a git repository or remote "origin" is not set')

    regex_match = re.match(
        GIT_REPOSITORY_REGEX,
        git_remote_origin_url
    )

    if regex_match is None:
        raise_error('Could not get remote "origin" url from git repository')

    repository_name = f'{regex_match.group(4)}/{regex_match.group(5)}'

    return repository_name


def raise_error(message):
    print(message)
    raise RuntimeError(message)


def first(iterable):
    try:
        return next(iterable)
    except StopIteration:
        return None


def main():
    parser = argparse.ArgumentParser(
        description='1password-secrets is a set of utilities to sync 1Password secrets.'
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    fly_parser = subparsers.add_parser('fly', help='manage fly secrets')
    fly_parser.add_argument('action', type=str, choices=['import', 'edit'])
    fly_parser.add_argument('app_name', type=str, help='fly application name')

    local_parser = subparsers.add_parser('local', help='manage local secrets')
    local_parser.add_argument('action', type=str, choices=['get', 'push'])

    args = parser.parse_args()

    try:
        if args.subcommand == 'fly':
            if args.action == 'import':
                import_1password_secrets_to_fly(args.app_name)
            elif args.action == 'edit':
                edit_1password_secrets(args.app_name)
        elif args.subcommand == 'local':
            if args.action == 'get':
                get_local_secrets()
            elif args.action == 'push':
                push_local_secrets()
    except Exception:
        sys.exit(1)


if __name__ == '__main__':
    main()
