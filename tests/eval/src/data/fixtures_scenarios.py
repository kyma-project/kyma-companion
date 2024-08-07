from src.models.evaluation.scenario import ScenarioList, Scenario
from src.models.evaluation.expectation import Expectation, ExpectationList
from src.models.evaluation.category import Category
import src.data.fixtures_problems as problems

NGINX_IMAGE_TYPO = Scenario(
    scenario_id="nginx-image-typo",
    problem=problems.NGINX_WRONG_IMAGE,
    expectations=ExpectationList(
        items=[
            Expectation(
                expectation_id="image-does-not-exist",
                statement="points out that the image ngix does not exist.",
                categories=[Category.PROBLEM_FINDING, Category.PLAIN_K8S],
                weight=1,
            ),
            Expectation(
                expectation_id="image-typo",
                statement="points out that there is a typo in the image name",
                categories=[Category.PROBLEM_FINDING, Category.PLAIN_K8S],
                weight=1,
            ),
            Expectation(
                expectation_id="propose-nginx",
                statement="points out that the image name should be 'nginx'",
                categories=[Category.SOLUTION_FINDING, Category.PLAIN_K8S],
                weight=2,
            ),
            Expectation(
                expectation_id="basic-yaml",
                statement="contains some yaml formatted code",
                categories=[
                    Category.SOLUTION_FINDING,
                    Category.YAML,
                    Category.PLAIN_K8S,
                ],
                weight=1,
            ),
            Expectation(
                expectation_id="complete-yaml",
                statement="contains a complete yaml formatted pod definition",
                categories=[
                    Category.SOLUTION_FINDING,
                    Category.YAML,
                    Category.PLAIN_K8S,
                ],
                weight=3,
            ),
            Expectation(
                expectation_id="complete-yaml-nginx",
                statement="contains a complete yaml formatted pod definition, that has the image set to 'nginx', the name set to 'mypod', and the namespace set to 'myns'",
                categories=[
                    Category.SOLUTION_FINDING,
                    Category.YAML,
                    Category.PLAIN_K8S,
                ],
                weight=5,
            ),
        ]
    ),
)

WHOAMI_WRONG_QUOTA = Scenario(
    scenario_id="whoami-wrong-quota",
    problem=problems.WHOAMI_WRONG_QUOTA,
    expectations=ExpectationList(
        items=[
            Expectation(
                expectation_id="quota-too-low",
                statement="points out that the quota is too low",
                categories=[Category.PROBLEM_FINDING, Category.PLAIN_K8S],
                weight=1,
            ),
            Expectation(
                expectation_id="propose-higher-quota",
                statement="points out that the quota should have a cpu limit should be set to a value higher than 50m",
                categories=[Category.SOLUTION_FINDING, Category.PLAIN_K8S],
                weight=2,
            ),
            Expectation(
                expectation_id="basic-yaml",
                statement="contains some yaml formatted code",
                categories=[
                    Category.SOLUTION_FINDING,
                    Category.YAML,
                    Category.PLAIN_K8S,
                ],
                weight=1,
            ),
            Expectation(
                expectation_id="fixed-yaml-nginx",
                statement="contains a complete yaml formatted resource quota definition, with the cpu limit set to 1",
                categories=[
                    Category.SOLUTION_FINDING,
                    Category.YAML,
                    Category.PLAIN_K8S,
                ],
                weight=3,
            ),
            Expectation(
                expectation_id="complete-yaml-nginx",
                statement="contains a complete yaml formatted resource quota definition, with the cpu limit set to 1, the namespace set to whoami, and the name set to whoami-resource-quota",
                categories=[
                    Category.SOLUTION_FINDING,
                    Category.YAML,
                    Category.PLAIN_K8S,
                ],
                weight=5,
            ),
        ]
    ),
)

KYMA_APP_FUNC_WITH_SYNTAX_ERROR = Scenario(
    scenario_id="kyma-app-func-with-syntax-error",
    problem=problems.KYMA_APP_SYNTAX_ERROR,
    expectations=ExpectationList(
        items=[
            Expectation(
                expectation_id="syntax-error",
                statement="points out that there is a syntax error in the function code",
                categories=[Category.PROBLEM_FINDING, Category.KYMA],
                weight=1,
            ),
            Expectation(
                expectation_id="propose-fix",
                statement="points out that the function tries to use undefined Dates function",
                categories=[Category.SOLUTION_FINDING, Category.KYMA],
                weight=2,
            ),
            Expectation(
                expectation_id="basic-yaml",
                statement="contains some yaml formatted code",
                categories=[
                    Category.SOLUTION_FINDING,
                    Category.YAML,
                    Category.KYMA,
                ],
                weight=1,
            ),
            Expectation(
                expectation_id="fixed-yaml",
                statement="contains a complete yaml formatted app function definition, with some definition for the Dates function",
                categories=[
                    Category.SOLUTION_FINDING,
                    Category.YAML,
                    Category.KYMA,
                ],
                weight=5,
            ),
        ]
    ),
)

KYMA_APP_WRONG_LANGUAGE = Scenario(
    scenario_id="kyma-app-wrong-language",
    problem=problems.KYMA_APP_WRONG_LANGUAGE,
    expectations=ExpectationList(
        items=[
            Expectation(
                expectation_id="wrong-lang",
                statement="points out that the language is set to python",
                categories=[Category.PROBLEM_FINDING, Category.KYMA],
                weight=1,
            ),
            Expectation(
                expectation_id="propose-fix",
                statement="points out that the language should be set to nodejs",
                categories=[Category.SOLUTION_FINDING, Category.KYMA],
                weight=1,
            ),
            Expectation(
                expectation_id="basic-yaml",
                statement="contains some yaml formatted code",
                categories=[
                    Category.SOLUTION_FINDING,
                    Category.YAML,
                    Category.KYMA,
                ],
                weight=1,
            ),
            Expectation(
                expectation_id="fixed-yaml",
                statement="contains a complete yaml formatted kyma function definition, with the language set to nodejs",
                categories=[
                    Category.SOLUTION_FINDING,
                    Category.YAML,
                    Category.KYMA,
                ],
                weight=5,
            ),
        ]
    ),
)

ALL_SCENARIOS = ScenarioList(
    items=[
        NGINX_IMAGE_TYPO,
        WHOAMI_WRONG_QUOTA,
        KYMA_APP_FUNC_WITH_SYNTAX_ERROR,
        KYMA_APP_WRONG_LANGUAGE,
    ]
)

LATEST_SCENARIOS = ScenarioList(
    items=[
        NGINX_IMAGE_TYPO,
    ]
)
