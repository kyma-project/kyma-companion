# Testing for prompt engineering

## Overview
The framework comes with three functionalities:
- **Evaluation**: evolute the problem solving skills of an ai model (let's call it *assistant*) by handing over predefined problems to it, take its response, and compare it against a set of predefined expectations via another ai model (we call this one *evaluator*).
- **Validation**: to see if an *evaluator* can be trusted and to find the right model for the job of an *evaluator*, we check its capabilities at comparing responses against expectations. For this, predefined answers are checked against the same predefined expectations from evaluation. The result is compared against the predefined wanted results. This is done via another model (and this one we call *validator*).
- **Mock Assistant**: just for development reason we have an mock *assistant*, that can solve the problems.

## Data structure and logic
### Evaluation
The base of testing is the testing data. For that reason understanding the underlying data models is important.

The base of validation is the [`Scenario`](./src/models/evaluation/scenario.py) class, which contains the `problem` that will be handed over to the assistant. It also carries an unique `scenario_id` that helps to identify it.

```python
scenario=Scenario(
    scenario_id = "boring_food"
    problem="my food is bland",
    ...
)
```

Alongside of the `problem` are some [`Expectation`s](./src/models/evaluation/expectation.py). And expectation holds an `statement`. The `statement` is what the `Evaluator` is using to check the *assistant* response against. 

```python
scenario=Scenario(
    scenario_id="boring_food"
    problem="my food is bland",
    expectations=ExpectationList(
        items=[
            Expectation(
                statement="points out that spices are missing",
                ...
            ),
        ]
    ),
    ...
)
```

Not every expectation is equally hard to match. For that reason expectations have a `weight` that is a positive integer Also, for clearer results in the evaluation, every 
expectation has `categories` assigned to it.

```python
scenario=Scenario(
    scenario_id="boring_food"
    problem="my food is bland",
    expectations=ExpectationList(
        items=[
            Expectation(
                expectation_id="missing_spices"
                statement="points out that spices are missing",
                weight=1
                categories=[Category.PROBLEM_FINDING]
            ),
            Expectation(
                expectation_id="add_salt"
                statement="points out that salt should be added",
                weight=1
                categories=[Category.SOLUTION_FINDING]
            ),
        ]
    ),
    ...
)
```

As described earlier, for [`evaluation`](./src/logic/evaluate.py) the problem is send to the *assistant*. The returning response is then stored at the `scenarios` `assistant_responses` property via the `add_new_assistant_response` method. Multiple responses can be stored at the alongside so that multiple separate evaluations can be conducted at the same time.

The actual [`evaluation`](./src/logic/evaluate.py) will finally store the results in the `evaluation_results` field.

`Scenario`s are aggregated in a `ScenarioList`. It can compute the score of a scenario (`get_scores_by_scenario_id`) or the score by category for all scenarios (`get_scores_by_category`).

### Validation
To validate a potential *evaluator*, *validation* is conducted. The needed data is stored in a class called `Validation`. It holds the underlying `scenario` (that is used while *evaluation*) and a number of [`mock_responses`](./src/models/validation/mock_response.py). A mock response holds the `mock response content` itself, that mimics the behavior of the *assistant* during *validation*. It also contains a unique `mock_response_id`.

```python
evaluation=Evaluation(
    scenario=bland_food
    mock_responses=MockResponseList(items=[
        MockResponse(
            mock_response_id = "simple_response",
            mock_response_content = "Your food is bland because it lacks spices. Your need to add some salt.",
        ),
    ])
    ...
)
```

The `MockResponse` contains `wanted_results`. A `WantedResult` is tied to an `Expectation` via the `expectation_id`. It further contains two bools that indicate if we want a match (`wanted_result`) and if we got a match (`actual_result`). Finally we have a weight again, that is a positive integer.

```python
evaluation=Evaluation(
    scenario=bland_food,
    mock_responses=MockResponseList(items=[
        MockResponse(
            mock_response_id = "simple_response",
            mock_response_content="Your food is bland because it lacks spices. Your need to add some salt.",
            wanted_results=WantedResultList(items=[
                WantedResult(
                    expectation_id="missing_spices",
                    wanted_result=True,
                    actual_result=None,
                    weight=1,
                )
            ])
        ),
    ]),
)
```

The `validation` will take a `Scenario` for its `expectations`, but it will ignore the actual `problem`. Further, it will take the `mock_response` and tries to match them against the `expectations`. The result will be stored in the `actual_result`. It will produce a weighted score by comparing the `wanted_result` the `actual_result`
