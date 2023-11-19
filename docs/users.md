# user authentication system

## First Time Setup

By default, the server will create a new admin account using the username
and password values defined in `dashlive/server/settings.py`. You will need
to use that username and password to log into the server and then change the
password. From the [users](http://localhost:8080/users) page can then be
used to add additional users to the system.

## User Groups

The server provides three groups to which each user can become a member:

| Group Name | Feature |
| --- | --- |
| admin | can create and edit other users |
| media | can create and edit streams |
| user | no specific functionality | 

### admin

A member of this group can create and edit other users.

When creating a new user the "must change password" option can be set to
force the user to change their password upon first login.

### media

A member of the media group is allowed to create and modify streams.
The intention of having a media group is to avoid accidental modification
of streams by restricting which accounts can modify them.

### user

At the moment, this group doesn't provide any specific functionality. All
users are a member of this group. In the future this group might be used
to limit access to features such as the validator, so that only registered
users can use it.


