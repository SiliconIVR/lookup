# lookup
A simple CLI to look up Genesys Cloud data.

Currently limited to:
   * Queue by name "contains" search
   * Queue by ID - may include more than one id.
   * User by name "contains" search
   * User by ID - may include more than one id.
   * Conversation data by ID - will return participants, start time, and attributes.

Requires Python3.10+ 

Genesys Cloud oAuth Client Credentials with Employee role and a new role with the following permissions:
   * Analytics > Conversation Detail > View
   * Conversation > Communication > View
   * Routing > Queue > Search
   * Routing > Queue > View

