# LangFuse
- [Official Website](https://langfuse.com/)
- [Official Docs](https://langfuse.com/docs)

## Setup
### Run a local instance of LangFuse
First, in the base directory of your local copy of the `Kyma-Companion` repository open or create the `.env` file:
```bash
vi .env
```
and paste the following:
```
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_HOST=http://localhost:3000
```
Keep this open, we will need it in a minute.

To run LangFuse locally you need to download the source code from github.com. These are the required steps:
```bash
# The directory where we will clone the source code to; change as you need.
export LANGFUSE_DIR=~/src/github.com/langfuse
# Create the parent directory.
mkdir -p $LANGFUSE_DIR
# Change to the newly created directory.
cd $LANGFUSE_DIR
# Clone the repository.
git clone https://github.com/langfuse/langfuse.git
# Enter the directory of the repository.
cd langfuse
# Start the database and LangFuse server.
docker compose up --wait
# Create a new account.
open http://localhost:3000/auth/sign-up
```
Hit the `+ New project` button, give your project a name, and hit `Create`. On the next page you will find the values for `LANGFUSE_SECRET_KEY` and `LANGFUSE_PUBLIC_KEY`; copy them into your `.env` file.

If you already have a local copy of the LangFuse repository, don't forget to `fetch` and `pull` the latest changes, since it gets frequently updated. Then just run:
```bash
docker compose up --wait
open http://localhost:3000/auth/sign-up
```
from the directory of you local copy.

You can now watch the traces of the `Kyma-Companion` from http://localhost:3000.


