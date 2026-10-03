"""Evaluate the YAML's delivery gate for actual Azure Pipelines event combinations."""
import ast
import re
from pathlib import Path

import pytest

YAML = (Path(__file__).resolve().parents[2] / 'azure-pipelines.yml').read_text()
CONDITION = re.search(r'^\s+condition: (.+)$', YAML, re.MULTILINE).group(1)


def permits(branch, reason, successful=True):
    expression = CONDITION.replace('and(', 'all_of(').replace('in(', 'one_of(')
    variables = {'Build.SourceBranch': branch, 'Build.Reason': reason}
    functions = {
        'all_of': lambda *args: all(args),
        'eq': lambda left, right: left == right,
        'one_of': lambda value, *options: value in options,
        'succeeded': lambda: successful,
    }

    def evaluate(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Subscript) and node.value.id == 'variables':
            return variables[evaluate(node.slice)]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return functions[node.func.id](*(evaluate(arg) for arg in node.args))
        raise AssertionError('Unsupported delivery gate expression')

    return evaluate(ast.parse(expression, mode='eval').body)


@pytest.mark.parametrize(('branch', 'reason', 'successful', 'expected'), [
    ('refs/heads/develop', 'IndividualCI', True, True),
    ('refs/heads/develop', 'BatchedCI', True, True),
    ('refs/heads/develop', 'IndividualCI', False, False),
    ('refs/heads/develop', 'PullRequest', True, False),
    ('refs/pull/17/merge', 'PullRequest', True, False),
    ('refs/heads/feature/test', 'IndividualCI', True, False),
    ('refs/heads/main', 'IndividualCI', True, False),
    ('refs/heads/develop', 'Manual', True, False),
])
def test_delivery_gate(branch, reason, successful, expected):
    assert permits(branch, reason, successful) is expected


def test_agent_and_environment_guards():
    assert 'vmImage: ubuntu-24.04' in YAML
    assert 'ubuntu-latest' not in YAML
    assert 'enableDevDelivery' not in YAML
    assert 'lockBehavior: sequential' in YAML
    assert 'environment: openthread-dev' in YAML
    assert 'fetchDepth: 2' in YAML
