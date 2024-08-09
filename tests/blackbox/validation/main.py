"""Main is to demo the mock assistant, evaluate its responses, and calibrate it."""
import os

from dotenv import load_dotenv

from utils.data_loader import load_data
from validation.validation import Validation

load_dotenv()

from utils.models import get_gpt35_model, get_gpt4o_model, get_models  # noqa
from src.validation.validator import ModelValidator  # noqa


def main():
    """Main function to evaluate the model's responses to the given scenarios."""
    llms = get_models()
    data = load_data(os.getenv("VALIDATION_DATA_DIR", "./tests/blackbox/data/validation"))
    validation = Validation(llms, data)
    validation.validate()
    print(validation.model_scores)


if __name__ == "__main__":
    main()
