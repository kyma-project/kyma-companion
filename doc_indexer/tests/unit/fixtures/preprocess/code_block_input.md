# Code Block Preservation Test

This text has a comment <!-- not a comment --> outside a code block.

This link [not](a-link.md) is outside a code block.

```python
# This comment inside a code block must not be touched
x = "hello"  <!-- not a comment -->
result = [not](a-link.md)
```

After the code block.
