i want to build a tool that i will interact with primarily in a slack channel.

i want a service that watches and collects several documentation source - some are directories and some are documentation
web sites - and then makes the documentation available to an agent, so that i can have a conversation with the agent and
ask it questions about the topics documented (software scope, architecture, capabilities, etc)

a development journal is also a form of documentation.

In order to employ "separation of concerns" and not tightly couple the tool to slack or a client, i want to create an mcp
server.

Advise me how to architect this.

I think there will be 3 layers

- ingestion - scrape sites, watch directories, pick up changes automatically
- knowledge base - a database and/or a vector store
- interface (mcp server)

regarding the knowledge base (kb) i want to be able to answer structures questions like "when was documentation about X
created" and also natural language questions like "does service x talk to service y" or "what ports are used on foo vm"

the first client of the mcp server will be an agent run by the nanoclaw assistant, the ui will be a slack channel.
