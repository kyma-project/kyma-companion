"""
Shared test utilities for integration tests.

This module provides common base classes and utilities for creating clean,
readable test parametrization using the TestCase pattern.
"""


class BaseTestCase:
    """
    Base class for test cases following the TestCase pattern.

    The TestCase pattern provides clean test output by using pytest's
    parametrize feature with a single parameter. The first attribute (name)
    becomes the test ID displayed in pytest output.

    Usage:
        class MyTestCase(BaseTestCase):
            def __init__(self, name: str, param1, param2, ...):
                super().__init__(name)
                self.param1 = param1
                self.param2 = param2

        def create_test_cases():
            return [
                MyTestCase("Should do X when Y", value1, value2),
                MyTestCase("Should handle Z condition", value3, value4),
            ]

        @pytest.mark.parametrize("test_case", create_test_cases())
        def test_something(test_case: MyTestCase):
            result = function(test_case.param1)
            assert result == test_case.param2, f"{test_case.name}: assertion message"
    """

    def __init__(self, name: str):
        """
        Initialize the test case with a descriptive name.

        Args:
            name: A concise, descriptive name for the test case.
                  This will appear in pytest output as the test ID.
                  Use imperative form like "Should do X when Y".
        """
        self.name = name

    def __repr__(self):
        """Return string representation using the test name."""
        return self.name
