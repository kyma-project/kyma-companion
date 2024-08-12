"""Main is to demo the mock assistant, evaluate its responses, and calibrate it."""

import argparse
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from validation.utils.data_loader import load_data  # noqa
from validation.validation import Validation  # noqa
from validation.utils.models import get_models  # noqa
from validation.validator import ModelValidator  # noqa


async def main(full_report: bool = False):
    models = get_models()
    data = load_data(os.getenv("VALIDATION_DATA_PATH", "./data/validation"))
    validation = Validation(models, data)
    await validation.validate()
    validation.print_report()
    if full_report:
        validation.print_full_report()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full_report", action="store_true", help="Flag to print the full report"
    )
    args = parser.parse_args()
    asyncio.run(main(args.full_report))
