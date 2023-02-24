# 1password-secrets

1password-secrets is a set of utilities to sync 1Password secrets. It enables:

 - Seamless sharing of *local* secrets used for development.
   Developers starting out in a project can just use this tool to retrieve the `.env` file needed for local development.
   Likewise it is also simple to push back any local changes to the 1password vault.

 - More secure and simpler method of managing Fly secrets.
   By default, Fly secrets must be managed by `flyctl`. This means that setting secrets in production, developers must use `flyctl` passing credentials via arguments - risking credentials being stored in their histories. Alternatively one must secrets in a file and run `flyctl secrets import`. This works well, but you must ensure everything is synched to a secret/password manager and then delete the file.
   1password-secrets enables a leaner management of secrets via 1password. Via an app name, automatically finds and imports secrets in an 1password *secure note* to Fly. This way you ensure developers always keep secrets up-to-date and never lost files in their computer.

Motivation: Using 1password for this avoids the need for another external secret management tool. And keeps the access control in a centralised place that we already use.

## Getting started
### Requirements

 - Install the required dependencies:
   
   1Password >= `8.9.13`
   
   1Password CLI >=  `2.13.1`
   
   flyctl >= `0.0.451`

   ```
   brew install --cask 1password 1password-cli && \
   brew install flyctl
   ```

 - Allow 1Password to connect to 1Password-CLI by going to `Settings` -> `Developer` -> `Command-Line Interface (CLI)` and select `Connect with 1Password CLI`.

 - Sign into your 1Password and Fly account (if you wish to use the fly integration).

### Installation

`pip install 1password-secrets`

## Usage

### Local

From within a valid git repository with remote "origin" ending in `<owner>/<repo>.git`, 1password-secrets will be able to `get` and `push` secrets to a 1password secure note containing  `repo:<owner>/<repo>` in its name. By default it syncs to `./.env` file, this can overridden with a `file_name` field containing the desired relative file path.

To get secrets from 1Password, run:
`1password-secrets local get`

To push the local changes to 1Password, run:
`1password-secrets local push`

### Fly

Make sure you have a Secure Note in 1Password with `fly:<fly-app-name>` in the title. `fly-app-name` is the name of your fly application.

To import secrets to fly, run:
`1password-secrets fly import <fly-app-name>`

Secrets can be edit directly on 1Password app or using the command:
`1password-secrets fly edit <fly-app-name>`
