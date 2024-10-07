import argparse
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from validation.utils.data_loader import load_data  # noqa
from validation.model_validation import create_validation  # noqa
from validation.utils.models import get_models  # noqa
from validation.validator import ModelValidator  # noqa

DEFAULT_DATA_DIR: str = "./data/namespace-scoped"


async def main(full_report: bool = False) -> None:
    data = load_data(os.getenv("VALIDATION_DATA_PATH", DEFAULT_DATA_DIR))
    models = get_models()
    validation = create_validation(models, data)
    await validation.validate()
    validation.print_report()
    if full_report:
        validation.print_full_report()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full_report", action="store_true", help="Flag to print the full report")
    args = parser.parse_args()
    asyncio.run(main(args.full_report))
