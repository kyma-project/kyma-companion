"""Main is to demo the mock assistant, evaluate its responses, and calibrate it."""
from dotenv import load_dotenv

from validation.validation import Validation

load_dotenv()

from src.validation.chat_models import get_gpt35_model, get_gpt4o_model, get_models  # noqa
from src.validation.validator import ModelValidator  # noqa


def main():
    """Main function to evaluate the model's responses to the given scenarios."""
    llms = get_models()
    validation = Validation(llms)
    validation.validate()


if __name__ == "__main__":
    main()
