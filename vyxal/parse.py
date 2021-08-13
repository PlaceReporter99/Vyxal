"""
File: parse.py
Description: Once Vyxal programs have been tokenised using lexer.py, the
next step is to group the tokens into their corresponding structures.
This is done by treating the tokens as a queue and dequeuing tokens
until a predicate is matched for structures.
"""

from __future__ import annotations

import re
import string
from collections import deque
from enum import Enum

try:
    import lexer
    import structure
except:
    import vyxal.lexer as lexer
    import vyxal.structure as structure


STRUCTURE_INFORMATION = {
    # (Name, Closing character)
    "[": (structure.IfStatement, "]"),
    "(": (structure.ForLoop, ")"),
    "{": (structure.WhileLoop, "}"),
    "@": (structure.FunctionCall, ";"),
    "λ": (structure.Lambda, ";"),
    "ƛ": (structure.LambdaMap, ";"),
    "'": (structure.LambdaFilter, ";"),
    "µ": (structure.LambdaSort, ";"),
    "°": (structure.FunctionReference, ";"),
    "⟨": (structure.ListLiteral, "⟩"),
}

CLOSING_CHARACTERS = "".join([v[1] for v in STRUCTURE_INFORMATION.values()])
OPENING_CHARACTERS = "".join(STRUCTURE_INFORMATION.keys())
MONADIC_MODIFIERS = list("v⁽&~ß")
DYADIC_MODIFIERS = list("₌‡₍")
TRIADIC_MODIFIERS = list("≬")
# The modifiers are stored as lists to allow for potential digraph
# modifiers.


def process_parameters(tokens: list[lexer.Token]) -> list[str]:
    """
    Turns the tokens from the first branch of a function defintion
    structure and returns the name and parameters.

    Parameters
    ----------

    tokens : list[lexer.Token]
        The tokens to turn into the parameter details

    Returns
    -------

    list[str]
        [name, parameters...]
    """
    token_values = [token.value for token in tokens]
    branch_data = "".join(token_values)
    components = branch_data.split(":")

    parameters = [components[0]]
    # this'll be the list that is returned

    for parameter in components[1:]:
        if parameter.isnumeric() or parameter == "*":
            parameters.append(parameter)
        else:
            parameters.append(re.sub(r"[A-z_]", "", parameter))

    return parameters


def variable_name(tokens: list[lexer.Token]) -> str:
    """
    Concatenates the value of all tokens and removes non-alphabet/non-
    underscore characters from the result.

    Parameters
    ----------

    tokens : list[lexer.Token]
        The tokens to turn into a single variable name.

    Returns
    -------

    str
        The token values concatenated together with non `[A-z_]`
        characters removed.
    """

    token_values = [token.value for token in tokens]
    name = "".join(token_values)
    return_name = ""

    for char in name:
        if char in string.ascii_letters + "_":
            return_name += char

    return return_name


def parse(tokens: list[lexer.Token]) -> list[structure.Structure]:
    """
    Transforms a tokenised Vyxal program into a list of Structures.

    Parameters
    ----------

    tokens : list[lexer.Token]
        This is the tokens that have been generated by the lexer.

    Returns
    -------

    list[Structure]
        A list of structures within the program.
    """
    structures = []
    bracket_stack = []  # all currently open structures
    tokens = deque(tokens)
    branches = []  # This will serve as a way
    # to keep track of all the
    # branches of the structure

    structure_name = structure.GenericStatement

    while tokens:
        head = tokens.popleft()
        if head.value in OPENING_CHARACTERS:
            structure_name = STRUCTURE_INFORMATION[head.value][0]
            bracket_stack.append(STRUCTURE_INFORMATION[head.value][1])
            branches = [[]]
            # important: each branch is a list of tokens, hence why
            # it's a double nested list to start with - each
            # token gets appended to the last branch in the branches
            # list.

            while tokens and bracket_stack:
                # that is, while there are still tokens to consider,
                # while we are still in the structure and while the
                # next value isn't the closing character for the
                # structure (i.e. isn't Token(TokenType.GENERAL, "x"))
                # where x = the corresponding closing character).
                token: lexer.Token = tokens.popleft()
                if token.value in OPENING_CHARACTERS:
                    branches[-1].append(token)
                    bracket_stack.append(STRUCTURE_INFORMATION[token.value][-1])

                elif token.value == "|":
                    if len(bracket_stack) == 1:
                        # that is, we are in the outer-most structure.
                        branches.append([])
                    else:
                        branches[-1].append(token)
                elif token.value in CLOSING_CHARACTERS:
                    # that is, it's a closing character that isn't
                    # the one we're expecting.
                    if token.value == bracket_stack[-1]:
                        # that is, if it's closing the inner-most
                        # structure

                        bracket_stack.pop()
                        if bracket_stack:
                            branches[-1].append(token)
                else:
                    branches[-1].append(token)
            # Now, we have to actually process the branch(es) to make
            # them _nice_ for the transpiler.

            """
            Structures that have to be manually processed are:

            - For loops: if there are two+ branches, the first must be
                         made into a valid variable name (alpha + _).
            - Functions: if there are two+ branches, the first must have
                         its paramters extracted from the first branch.
            - Function References: the name must be turned into a valid
                                   function name.
            - Non-standard Lambdas: these must have their corresponding
                                    element appended after the normal
                                    lambda is appended to the structure
                                    list. This is because non-standard
                                    lambdas are just normal lambdas +
                                    an element.
            """
            after_token = None
            if structure_name == structure.ForLoop:
                if len(branches) > 1:
                    branches[0] = variable_name(branches[0])
                branches[-1] = parse(branches[-1])
            elif structure_name == structure.FunctionCall:
                branches[0] = process_parameters(branches[0])
                if len(branches) > 1:
                    branches[-1] = parse(branches[-1])
            elif structure_name == structure.FunctionReference:
                branches[0] = variable_name(branches[0])
            elif structure_name == structure.Lambda:
                if len(branches) == 1:
                    # that is, there is only a body - no arity
                    branches.insert(0, "1")
                else:
                    branches[0] = branches[0][0].value
                branches[1] = parse(branches[1])
            elif structure_name == structure.LambdaMap:
                branches.insert(0, "1")
                branches[1] = parse(branches[1])
                structure_name = structure.Lambda
                after_token = structure.GenericStatement(
                    [lexer.Token(lexer.TokenType.GENERAL, "M")]
                )
                # laziness ftw
            elif structure_name == structure.LambdaFilter:
                branches.insert(0, "1")
                branches[1] = parse(branches[1])
                structure_name = structure.Lambda
                after_token = structure.GenericStatement(
                    [lexer.Token(lexer.TokenType.GENERAL, "F")]
                )
                # laziness ftw
            elif structure_name == structure.LambdaSort:
                branches.insert(0, "1")
                branches[1] = parse(branches[1])
                structure_name = structure.Lambda
                after_token = structure.GenericStatement(
                    [lexer.Token(lexer.TokenType.GENERAL, "ṡ")],
                )
                # laziness ftw
            else:
                branches = list(map(parse, branches))

            structures.append(structure_name(branches))
            if after_token is not None:
                structures.append(after_token)
        elif head.value in MONADIC_MODIFIERS:
            # the way to deal with all modifiers is to parse everything
            # after the modifier and dequeue as many structures as
            # needed to satisfy the arity of the modifier. It's import-
            # -ant that you break the while loop after dealing with the
            # modifier.

            remaining = parse(tokens)
            if head.value == "⁽":
                structures.append(structure.Lambda(["1", [[remaining[0]]]]))
            else:
                structures.append(
                    structure.MonadicModifier([head.value, [remaining[0]]])
                )
            structures += remaining[1:]
            break
        elif head.value in DYADIC_MODIFIERS:
            remaining = parse(tokens)
            if head.value == "‡":
                structures.append(
                    structure.Lambda(["1", [remaining[0], remaining[1]]])
                )
            else:
                structures.append(
                    structure.DyadicModifier(
                        [head.value, [remaining[0], remaining[1]]]
                    )
                )
            structures += remaining[2:]
            break
        elif head.value in TRIADIC_MODIFIERS:
            remaining = parse(tokens)
            if head.value == "‡":
                structures.append(
                    structure.Lambda(
                        ["1", [remaining[0], remaining[1], remaining[2]]],
                    )
                )
            else:
                structures.append(
                    structure.TriadicModifier(
                        [
                            head.value,
                            [remaining[0], remaining[1], remaining[2]],
                        ],
                    )
                )
            structures += remaining[3:]
            break
        elif any((head.value in CLOSING_CHARACTERS, head.value in " |")):
            # that is, if someone has been a sussy baka
            # with their syntax (probably intentional).
            continue  # ignore it. This also ignores spaces btw
        else:
            structures.append(structure.GenericStatement([head]))

    return structures
