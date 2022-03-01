# Copyright 2021 AIPlan4EU project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""The ExpressionManager is used to create expressions.

All objects are memoized so that two syntactically equivalent expressions
are represented by the same object.
"""

import unified_planning
import unified_planning.model.types
import unified_planning.model.operators as op
from unified_planning.exceptions import UPTypeError, UPExpressionDefinitionError
from fractions import Fraction
from typing import Iterable, List, Union, Dict, Tuple

Expression = Union['unified_planning.model.fnode.FNode', 'unified_planning.model.fluent.Fluent', 'unified_planning.model.object.Object', 'unified_planning.model.action.ActionParameter', 'unified_planning.model.variable.Variable', bool, int, float, Fraction]
BoolExpression = Union['unified_planning.model.fnode.FNode', 'unified_planning.model.fluent.Fluent', 'unified_planning.model.action.ActionParameter', bool]

class ExpressionManager(object):
    """ExpressionManager is responsible for the creation of all expressions."""

    def __init__(self, env: 'unified_planning.environment.Environment'):
        self.env = env
        self.expressions: Dict['unified_planning.model.fnode.FNodeContent', 'unified_planning.model.fnode.FNode'] = {}
        self._next_free_id = 1

        self.true_expression = self.create_node(node_type=op.BOOL_CONSTANT,
                                                args=tuple(),
                                                payload=True)
        self.false_expression = self.create_node(node_type=op.BOOL_CONSTANT,
                                                 args=tuple(),
                                                 payload=False)
        return

    def _polymorph_args_to_tuple(self, *args: Union[Expression, Iterable[Expression]]) -> Tuple[Expression, ...]:
        """ Helper function to return a tuple of arguments from args.
        This function is used to allow N-ary operators to express their arguments
        both as a list of arguments or as a tuple of arguments: e.g.,
           And([a,b,c]) and And(a,b,c)
        are both valid, and they are converted into a tuple (a,b,c) """

        res = []
        for p in args:
            if isinstance(p, Iterable):
                res.extend(list(p))
            else:
                res.append(p)
        return tuple(res)

    def auto_promote(self, *args: Union[Expression, Iterable[Expression]]) -> List['unified_planning.model.fnode.FNode']:
        tuple_args = self._polymorph_args_to_tuple(*args)
        res = []
        for e in tuple_args:
            if isinstance(e, unified_planning.model.fluent.Fluent):
                res.append(self.FluentExp(e))
            elif isinstance(e, unified_planning.model.action.ActionParameter):
                res.append(self.ParameterExp(e))
            elif isinstance(e, unified_planning.model.variable.Variable):
                res.append(self.VariableExp(e))
            elif isinstance(e, unified_planning.model.object.Object):
                res.append(self.ObjectExp(e))
            elif isinstance(e, bool):
                res.append(self.Bool(e))
            elif isinstance(e, int):
                res.append(self.Int(e))
            elif isinstance(e, float):
                res.append(self.Real(Fraction(e)))
            elif isinstance(e, Fraction):
                res.append(self.Real(e))
            else:
                res.append(e)
        return res

    def create_node(self, node_type: int, args: Iterable['unified_planning.model.fnode.FNode'],
                    payload: Union['unified_planning.model.fluent.Fluent', 'unified_planning.model.object.Object', 'unified_planning.model.action.ActionParameter', 'unified_planning.model.variable.Variable', bool, int, Fraction, Tuple['unified_planning.model.variable.Variable', ...]] = None) ->'unified_planning.model.fnode.FNode':
        content = unified_planning.model.fnode.FNodeContent(node_type, args, payload)
        if content in self.expressions:
            return self.expressions[content]
        else:
            n =unified_planning.model.fnode.FNode(content, self._next_free_id)
            self._next_free_id += 1
            self.expressions[content] = n
            self.env.type_checker.get_type(n)
            return n

    def And(self, *args: Union[BoolExpression, Iterable[BoolExpression]]) -> 'unified_planning.model.fnode.FNode':
        """ Returns a conjunction of terms.
        This function has polimorphic n-arguments:
          - And(a,b,c)
          - And([a,b,c])
        Restriction: Arguments must be boolean
        """
        tuple_args = tuple(self.auto_promote(*args))

        if len(tuple_args) == 0:
            return self.TRUE()
        elif len(tuple_args) == 1:
            return tuple_args[0]
        else:
            return self.create_node(node_type=op.AND,
                                    args=tuple_args)

    def Or(self, *args: Union[BoolExpression, Iterable[BoolExpression]]) ->'unified_planning.model.fnode.FNode':
        """ Returns an disjunction of terms.
        This function has polimorphic n-arguments:
          - Or(a,b,c)
          - Or([a,b,c])
        Restriction: Arguments must be boolean
        """
        tuple_args = tuple(self.auto_promote(*args))

        if len(tuple_args) == 0:
            return self.FALSE()
        elif len(tuple_args) == 1:
            return tuple_args[0]
        else:
            return self.create_node(node_type=op.OR,
                                    args=tuple_args)

    def Not(self, expression: BoolExpression) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form:
                not expression
        Restriction: expression must be of boolean type
        """
        expression, = self.auto_promote(expression)
        if expression.is_not():
            return expression.arg(0)
        return self.create_node(node_type=op.NOT, args=(expression,))

    def Implies(self, left: BoolExpression, right: BoolExpression) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form:
            left -> right
        Restriction: Left and Right must be of boolean type
        """
        left, right = self.auto_promote(left, right)
        return self.create_node(node_type=op.IMPLIES, args=(left, right))

    def Iff(self, left: BoolExpression, right: BoolExpression) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form:
            left <-> right
        Restriction: Left and Right must be of boolean type
        """
        left, right = self.auto_promote(left, right)
        return self.create_node(node_type=op.IFF, args=(left, right))

    def Exists(self, expression: BoolExpression, *vars: 'unified_planning.model.variable.Variable') ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form:
            Exists (var[0]... var[n]) | expression
        Restriction: expression must be of boolean type and
                    vars must be of 'unified_planning.Variable' type
        """
        expressions = tuple(self.auto_promote(expression))
        if len(vars) == 0:
            raise UPExpressionDefinitionError(f"Exists of expression: {str(expression)} must be created with at least one variable, otherwise it is not needed.")
        for v in vars:
            if not isinstance(v, unified_planning.model.variable.Variable):
                raise UPTypeError("Expecting 'unified_planning.Variable', got %s", type(v))
        return self.create_node(node_type=op.EXISTS, args=expressions, payload=vars)

    def Forall(self, expression: BoolExpression, *vars: 'unified_planning.model.variable.Variable') ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form:
            Forall (var[0]... var[n]) | expression
        Restriction: expression must be of boolean type and
                    vars must be of 'unified_planning.Variable' type
        """
        expressions = tuple(self.auto_promote(expression))
        if len(vars) == 0:
            raise UPExpressionDefinitionError(f"Forall of expression: {str(expression)} must be created with at least one variable, otherwise it is not needed.")
        for v in vars:
            if not isinstance(v, unified_planning.model.variable.Variable):
                raise UPTypeError("Expecting 'unified_planning.Variable', got %s", type(v))
        return self.create_node(node_type=op.FORALL, args=expressions, payload=vars)

    def FluentExp(self, fluent: 'unified_planning.model.fluent.Fluent', params: Tuple[Expression, ...] = tuple()) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression for the given fluent and parameters.
        Restriction: parameters type must be compatible with the fluent signature
        """
        assert fluent.arity() == len(params)
        params_exp = self.auto_promote(*params)
        return self.create_node(node_type=op.FLUENT_EXP, args=tuple(params_exp), payload=fluent)

    def ParameterExp(self, param: 'unified_planning.model.action.ActionParameter') ->'unified_planning.model.fnode.FNode':
        """Returns an expression for the given action parameter."""
        return self.create_node(node_type=op.PARAM_EXP, args=tuple(), payload=param)

    def VariableExp(self, var: 'unified_planning.model.variable.Variable') ->'unified_planning.model.fnode.FNode':
        """Returns an expression for the given variable."""
        return self.create_node(node_type=op.VARIABLE_EXP, args=tuple(), payload=var)

    def ObjectExp(self, obj: 'unified_planning.model.object.Object') ->'unified_planning.model.fnode.FNode':
        """Returns an expression for the given object."""
        return self.create_node(node_type=op.OBJECT_EXP, args=tuple(), payload=obj)

    def TRUE(self) ->'unified_planning.model.fnode.FNode':
        """Return the boolean constant True."""
        return self.true_expression

    def FALSE(self) ->'unified_planning.model.fnode.FNode':
        """Return the boolean constant False."""
        return self.false_expression

    def Bool(self, value: bool) ->'unified_planning.model.fnode.FNode':
        """Return a boolean constant."""
        if type(value) != bool:
            raise UPTypeError("Expecting bool, got %s" % type(value))

        if value:
            return self.true_expression
        else:
            return self.false_expression

    def Int(self, value: int) ->'unified_planning.model.fnode.FNode':
        """Return an int constant."""
        if type(value) != int:
            raise UPTypeError("Expecting int, got %s" % type(value))
        return self.create_node(node_type=op.INT_CONSTANT, args=tuple(), payload=value)

    def Real(self, value: Fraction) ->'unified_planning.model.fnode.FNode':
        """Return a real constant."""
        if type(value) != Fraction:
            raise UPTypeError("Expecting Fraction, got %s" % type(value))
        return self.create_node(node_type=op.REAL_CONSTANT, args=tuple(), payload=value)

    def Plus(self, *args: Union[Expression, Iterable[Expression]]) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form:
            args[0] + ... + args[n]
        """
        tuple_args = tuple(self.auto_promote(*args))

        if len(tuple_args) == 0:
            return self.Int(0)
        elif len(tuple_args) == 1:
            return tuple_args[0]
        else:
            return self.create_node(node_type=op.PLUS,
                                    args=tuple_args)

    def Minus(self, left: Expression, right: Expression) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form: left - right."""
        left, right = self.auto_promote(left, right)
        return self.create_node(node_type=op.MINUS, args=(left, right))

    def Times(self, *args: Union[Expression, Iterable[Expression]]) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form:
            args[0] * ... * args[n]
        """
        tuple_args = tuple(self.auto_promote(*args))

        if len(tuple_args) == 0:
            return self.Int(1)
        elif len(tuple_args) == 1:
            return tuple_args[0]
        else:
            return self.create_node(node_type=op.TIMES,
                                    args=tuple_args)

    def Div(self, left: Expression, right: Expression) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form: left / right."""
        left, right = self.auto_promote(left, right)
        return self.create_node(node_type=op.DIV, args=(left, right))

    def LE(self, left: Expression, right: Expression) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form: left <= right."""
        left, right = self.auto_promote(left, right)
        return self.create_node(node_type=op.LE, args=(left, right))

    def GE(self, left: Expression, right: Expression) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form: left >= right."""
        left, right = self.auto_promote(left, right)
        return self.create_node(node_type=op.LE, args=(right, left))

    def LT(self, left: Expression, right: Expression) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form: left < right."""
        left, right = self.auto_promote(left, right)
        return self.create_node(node_type=op.LT, args=(left, right))

    def GT(self, left: Expression, right: Expression) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form: left > right."""
        left, right = self.auto_promote(left, right)
        return self.create_node(node_type=op.LT, args=(right, left))

    def Equals(self, left: Expression, right: Expression) ->'unified_planning.model.fnode.FNode':
        """ Creates an expression of the form: left == right."""
        left, right = self.auto_promote(left, right)
        return self.create_node(node_type=op.EQUALS, args=(left, right))