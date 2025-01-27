import argparse
import asyncio

from common.config import Config
from validation.model_validation import create_validation  # noqa
from validation.utils.data_loader import load_data  # noqa
from validation.utils.models import get_models  # noqa


async def main(full_report: bool = False) -> None:
    # load the configuration.
    config = Config()

    # load models and data.
    models = get_models(config)
    data = load_data(config.namespace_scoped_test_data_path)

    # create validation and run it.
    validation = create_validation(models, data)
    await validation.validate()
    validation.print_results()
    if full_report:
        validation.print_full_report()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full_report", action="store_true", help="Flag to print the full report"
    )
    args = parser.parse_args()
    asyncio.run(main(args.full_report))
