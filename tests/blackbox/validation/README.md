# Validation

## Overview
The framework comes with three functionalities:
- **Validation**: to see if an *evaluator* can be trusted and to find the right model for the job of an *evaluator*, we check its capabilities at comparing responses against expectations. For this, predefined answers are checked against the same predefined expectations from evaluation. The result is compared against the predefined wanted results. This is done via another model (and this one we call *validator*).