"""The main interface to the project - you run this file to run Vyxal programs
offline.

"""

import os
import sys
import traceback
import types

import vyxal.encoding
from vyxal.context import Context, TranspilationOptions
from vyxal.elements import *
from vyxal.helpers import *
from vyxal.LazyList import *
from vyxal.transpile import transpile

THIS_FOLDER = os.path.dirname(os.path.abspath(__file__)) + "/.."
sys.path.insert(1, THIS_FOLDER)


__all__ = ["execute_vyxal", "repl", "cli"]

FLAG_STRING = """ALL flags should be used as is (no '-' prefix)
    H    Preset stack to 100
    j    Print top of stack joined by newlines on end of execution
    L    Print top of stack joined by newlines (Vertically) on end of execution
    s    Sum/concatenate top of stack on end of execution
    M    Make implicit range generation and while loop counter start at 0 instead of 1
    m    Make implicit range generation end at n-1 instead of n
    Ṁ    Equivalent to having both m and M flags
    v    Use Vyxal encoding for input file
    c    Output compiled code
    f    Get input from file instead of arguments
    a    Treat newline seperated values as a list
    d    Print deep sum of top of stack on end of execution
    r    Makes all operations happen with reverse arguments
    S    Print top of stack joined by spaces on end of execution
    C    Centre the output and join on newlines on end of execution
    O    Disable implicit output
    o    Force implicit output
    l    Print length of top of stack on end of execution
    G    Print the maximum item of the top of stack on end of execution
    g    Print the minimum item of the top of the stack on end of execution
    W    Print the entire stack on end of execution
    Ṡ    Treat all inputs as strings
    R    Treat numbers as ranges if ever used as an iterable
    D    Treat all strings as raw strings (don't decompress strings)
    U    Treat all strings as UTF-8 byte sequences (also don't decompress strings)
    Ṫ    Print the sum of the entire stack
    ṡ    Print the entire stack, joined on spaces
    Z    With four argument vectorization where all arguments are lists, use zip(zip(a, b), zip(c, d)) instead of zip(a, b, c, d)
    J    Print the entire stack, separated by newlines
    t    Vectorise boolify on Lists
    P    Print lists as their python representation
    ḋ    Print rationals in their decimal form
    V    Variables are one character long
    E    Evaluate stdout as JavaScript (online interpreter only)
    Ḣ    Render stdout as HTML (online interpreter only)
    e    Use the file name as the program source (offline interpreter only)
    ?    If there is empty input, treat it as 0 instead of empty string.
    2    Make the default arity of lambdas 2
    3    Make the default arity of lambdas 3
    A    Run test cases on all inputs
    ~    Run test cases on all inputs and report whether results match expected outputs
    …    Limit list output to the first 100 items of that list
    !    Read program file as bitstring
    =    Print bitstring of program (online interpreter also updates byte count)
    5    Make the interpreter timeout after 5 seconds (online interpreter only)
    b    Make the interpreter timeout after 15 seconds (online interpreter only)
    B    Make the interpreter timeout after 30 seconds (online interpreter only)
    T    Make the interpreter timeout after 60 seconds (online interpreter only)
    ⋎    Print the current Vyxal version (offline interpreter only)
"""


def execute_vyxal(file_name, flags, inputs, output_var=None, online_mode=False):
    ctx = Context()
    stack = []
    ctx.online_output = output_var
    ctx.online = online_mode

    if online_mode:
        inputs = inputs.split("\n")  # have to do this here because file writing
        if inputs[0] == "":
            inputs = inputs[1:]

    # Handle input handling flags
    if "h" in flags:  # Help flag
        vy_print(FLAG_STRING, ctx=ctx)
        sys.exit(0)

    if "⋎" in flags:
        try:
            import tomllib as toml

            with open("pyproject.toml", "rb") as f:
                version = toml.load(f)["tool"]["poetry"]["version"]
            print(version)
        except ModuleNotFoundError:
            print("Use python 3.11+ to get the version")
        sys.exit(0)

    if "A" in flags:
        for inp in inputs:
            try:
                inps = ast.literal_eval(inp)
                if isinstance(inps, tuple):
                    inps = list(inps)
                else:
                    inps = [inps]
                inps = [vyxalify(x) for x in inps]
            except:
                inps = inp.split(", ")
            repred_inps = [
                repr(x) if not isinstance(x, LazyList) else repr(list(x))
                for x in inps
            ]
            if online_mode:
                ctx.online_output[1] += ", ".join(repred_inps) + " => "
            else:
                print(", ".join(repred_inps), end=" => ")
            execute_vyxal(
                file_name,
                flags.replace("A", ""),
                "\n".join(repred_inps) if online_mode else inps,
                output_var,
                online_mode,
            )
        return

    if "e" in flags:  # Program is file name
        code = file_name
    elif "!" in flags:  # Open file as bitstring
        if not online_mode:
            from subprocess import PIPE, Popen

            with open(file_name, "r", encoding="utf-8") as f:
                code = f.read()
            process = Popen(
                [
                    "java",
                    "-jar",
                    "vyxal/vyncode-1.0.0.jar",
                    "-m",
                    "decode",
                    "-p",
                    code,
                ],
                stdout=PIPE,
                stderr=PIPE,
            )
            result = process.communicate()
            code = result[0].decode("utf-8")
    elif "v" in flags:  # Open file using Vyxal encoding
        with open(file_name, "rb") as f:
            code = f.read()
            code = vyxal.encoding.vyxal_to_utf8(code)
    else:  # Open file using UTF-8 encoding:
        with open(file_name, "r", encoding="utf-8") as f:
            code = f.read()

    # Handle input handling flags

    if "f" in flags:  # Read inputs from file
        with open(inputs[0], "r", encoding="utf-8") as f:
            inputs = [x.replace("\r", "") for x in f.readlines()]

    ctx.original_args = inputs

    if "Ṡ" in flags:  # All inputs as strings
        inputs = list(map(str, inputs))
        ctx.inputs_as_strings = True
    else:
        inputs = list(map(lambda x: vy_eval(x, ctx), inputs))

    if "H" in flags:  # Pre-initalise stack to 100
        stack = [100]
    else:
        stack = []

    ctx.inputs[0][0] = inputs
    ctx.stacks.append(stack)

    # Handle runtime flags

    if "Ṁ" in flags:  # Implicit ranges are [0, n)
        ctx.range_start = 0
        ctx.range_end = 0

    elif "M" in flags:  # Implicit ranges are [0, n]
        ctx.range_start = 0

    elif "m" in flags:  # Implicit ranges are [1, n)
        ctx.range_end = 0

    ctx.reverse_flag = "r" in flags
    ctx.number_as_range = "R" in flags
    ctx.vectorise_boolify = "t" in flags  # see boolify in elements.py
    ctx.vyxal_lists = "P" not in flags
    ctx.print_decimals = "ḋ" in flags
    ctx.empty_input_is_zero = "?" not in flags
    ctx.array_inputs = "a" in flags
    ctx.double_zip_vectorize = "Z" in flags
    ctx.utf8strings = "U" in flags

    options = TranspilationOptions()
    options.dict_compress = "D" not in flags
    options.variables_as_digraphs = "V" in flags
    options.utf8strings = ctx.utf8strings
    ctx.transpilation_options = options

    if "2" in flags:
        ctx.default_arity = 2
    elif "3" in flags:
        ctx.default_arity = 3
    else:
        ctx.default_arity = 1

    if "=" in flags:
        if not online_mode:
            from subprocess import PIPE, Popen

            process = Popen(
                [
                    "java",
                    "-jar",
                    "vyxal/vyncode.jar",
                    "-m",
                    "encode",
                    "-p",
                    code,
                ],
                stdout=PIPE,
                stderr=PIPE,
            )
            result = process.communicate()
            print(result[0].decode("utf-8"))
            print("---")

    try:
        code = transpile(code, options)
    except Exception as e:  # skipcq: PYL-W0703
        if ctx.online:
            ctx.online_output[2] += "\n" + traceback.format_exc()
            sys.exit(1)
        else:
            raise e

    if "c" in flags:  # Show transpiled code
        if ctx.online:
            ctx.online_output[2] += code
        else:
            print(code + "\n")

    ctx.stacks.append(stack)
    if "~" in flags:
        case_regex = r"""(.+) ?(?:=>|-+>) ?(.+)"""
        if inputs[0][0] == "!":
            case_regex = inputs[0][1:]
            inputs = inputs[1:]

        for inp in inputs:
            mobj = re.match(case_regex, inp)
            if mobj is None or len(mobj.groups()) < 2:
                raise ValueError("Invalid test case: " + inp)
            in_val, out_val = mobj.groups()[0], mobj.groups()[1]
            try:
                inps = ast.literal_eval(in_val)
                if isinstance(inps, tuple):
                    inps = list(inps)
                else:
                    inps = [inps]
                inps = [vyxalify(x) for x in inps]
            except:
                inps = [vyxalify(x) for x in in_val.split(", ")]
            repred_inps = [repr(x) for x in inps]
            try:
                out_val = ast.literal_eval(out_val)
                if isinstance(out_val, tuple):
                    out_val = [vyxalify(x) for x in out_val]
                else:
                    out_val = vyxalify(out_val)
                out_val = repr(out_val)
            except:
                pass
            ctx.inputs[0][0] = inps[::]
            ctx.inputs[0][1] = 0
            if online_mode:
                slice_start = len(
                    ctx.online_output[1]
                )  # The number of characters already printed
                try:
                    execute_vyxal(
                        file_name,
                        flags.replace("~", ""),
                        "\n".join(repred_inps),
                        output_var,
                        online_mode,
                    )
                    ret = ctx.online_output[1][slice_start:][
                        :-1
                    ]  # That's what was printed when we called execute_vyxal
                    ctx.online_output[1] = ctx.online_output[1][:slice_start]
                    passes = out_val == ret
                    message = f"({inp}) ==> " + (
                        "PASS ✅"
                        if passes
                        else "FAIL ❌" + f" (expected {out_val}, got {ret})"
                    )
                    ctx.online_output[1] += message + "\n"
                except Exception as e:  # skipcq: PYL-W0703
                    ctx.online_output[1] += (
                        "\n" + inp + "\n" + traceback.format_exc()
                    )
                    sys.exit(1)
            else:
                try:
                    output = ["", ""]
                    execute_vyxal(
                        file_name,
                        flags.replace("~", ""),
                        "\n".join(repred_inps),
                        output,
                        True,
                    )
                    ret = output[1][
                        :-1
                    ]  # That's what was printed when we called execute_vyxal
                    passes = out_val == ret
                    message = f"({inp}) ==> " + (
                        "PASS ✅"
                        if passes
                        else "FAIL ❌" + f" (expected {out_val}, got {ret})"
                    )
                    print(message)
                except Exception as e:  # skipcq: PYL-W0703
                    print(traceback.format_exc())
                    raise
        return
    try:
        exec(code, locals() | globals())
    except Exception as e:  # skipcq: PYL-W0703
        if ctx.online:
            ctx.online_output[2] += "\n" + traceback.format_exc()
            sys.exit(1)
        else:
            raise

    if not ctx.printed and ctx.canvas.canvas != [[" "]]:
        vy_print(str(ctx.canvas), ctx=ctx)
        return

    originally_empty = not stack
    output = pop(stack, 1, ctx)

    if not (ctx.printed or "O" in flags) or "o" in flags:
        for flag in flags:
            if flag == "j":
                if isinstance(output, LazyList):
                    for item in output:
                        vy_print(item, ctx=ctx)
                    break
                else:
                    output = join(output, "\n", ctx=ctx)
            elif flag == "s":
                if not isinstance(output, LazyList) or not output.has_ind(0):
                    output = vy_sum(output, ctx)
                else:
                    acc = None
                    is_str = False
                    for elem in output:
                        if is_str:
                            vy_print(elem, end="", ctx=ctx)
                            continue
                        if acc is None:
                            # For the first element
                            acc = elem
                        else:
                            acc = add(acc, elem, ctx)
                        if isinstance(acc, str):
                            # We've encountered a string, now print that
                            # Everything else will also be immediately
                            # printed
                            vy_print(acc, end="", ctx=ctx)
                            is_str = True
                    output = acc
                    if not is_str:
                        vy_print(output, ctx=ctx)
                    break
            elif flag == "d":
                output = vy_sum(deep_flatten(output, ctx), ctx)
            elif flag == "Ṫ":
                if originally_empty:
                    output = []
                else:
                    stack.append(output)
                    output = vy_sum(stack, ctx)
                stack = [output]
            elif flag == "L":
                output = vertical_join(output, ctx=ctx)
            elif flag == "S":
                if isinstance(output, LazyList):
                    for item in output:
                        vy_print(item, end=" ", ctx=ctx)
                    break
                else:
                    output = join(output, " ", ctx)
            elif flag == "C":
                output = center(output, ctx)
                output = join(output, "\n", ctx)
            elif flag == "G":
                output = monadic_maximum(output, ctx)
            elif flag == "g":
                output = monadic_minimum(output, ctx)
            elif flag == "W":
                if originally_empty:
                    output = []
                else:
                    stack.append(output)
                    output = vy_str(stack, ctx)
            elif flag == "ṡ":
                if originally_empty:
                    output = []
                else:
                    stack.append(output)
                    output = join(stack, " ", ctx)
            elif flag == "J":
                if originally_empty:
                    output = []
                else:
                    stack.append(output)
                    output = join(stack, "\n", ctx)
            elif flag == "…":
                if vy_type(output, simple=True) is list:
                    output = output[:100]
            elif flag == "l":
                output = length(output, ctx)
            else:
                pass
        else:
            vy_print(output, ctx=ctx)


def repl():
    ctx, stack = Context(), []
    # This is called if a file isn't given, just like it used to.
    ctx.repl_mode = True
    while True:
        # Vyxal REPL ftw
        # Empty options is still required
        line = transpile(input(">>> "), TranspilationOptions())
        stack = []
        ctx.stacks.append(stack)  # Finally, a use case for assignment by
        # reference. Never thought I'd fine a time
        # when it wouldn't be an actual pain.
        print(line)
        exec(line, locals() | globals())

        res = []
        while stack:
            top = stack.pop()
            if isinstance(top, types.FunctionType):
                res.append(top(stack, top, ctx=ctx)[-1])
            else:
                res.append(top)
        res = res[::-1]

        vy_print(res, ctx=ctx)
        ctx.stacks.pop()


def cli():
    if len(sys.argv) > 1:
        file_name = sys.argv[1]
        flags = ""
        inputs = []

        if len(sys.argv) > 2:
            flags, inputs = sys.argv[2], sys.argv[3:]

        execute_vyxal(file_name, flags, inputs)
    else:
        repl()
