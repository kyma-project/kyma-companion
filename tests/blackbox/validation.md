# Evaluation

To find a model that can evaluate the test scenarios, we need to validate the best large language model (LLM) model. This can be done by running the validation tests.

## Usage

To run the validation, follow these steps:

1. Install dependencies:

    ```bash
    poetry install
    ```

2. Add LLMs data to `config/validation/models.yml` that are to be validated. The data should be in the following format:

   ```yaml
   - name: "gpt-4"
     deployment_id: {deployment_id_gpt_4}
   - name: "gemini-1.5-pro"
     deployment_id: {deployment_id_gemini_1_5_pro}
    ```

3. Prepare the `.env.validation` file based on the following template:

    ```
   AICORE_AUTH_URL=                     # AI-Core Auth URL.
   AICORE_BASE_URL=                     # AI-Core Base URL.
   AICORE_CLIENT_ID=                    # AI-Core Client ID.
   AICORE_CLIENT_SECRET=                # AI-Core Client Secret.
   AICORE_RESOURCE_GROUP=               # AI-Core Resource Group.
   
   VALIDATION_DATA_PATH=                # Path to the validation data folder, default is ./data/validation
   EVALUATION_DATA_PATH=                # Path to the evaluation data folder, default is ./data/evaluation
   MODEL_CONFIG_PATH=                   # Path to the model config file, default is ./config/validation/models.yml
    ```

3. Run the following command to set up the environment variables in your system:

    ```bash
    export $(xargs < .env.validation)
    ```

4. Run the validation:

    ```bash
   poetry run python src/run_validation.py
   # OR
   poetry shell
   python src/run_validation.py
    ```
