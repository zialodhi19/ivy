# general
import importlib
import inspect
import typing
from typing import List

from hypothesis import given, strategies as st

# local
import ivy
from .hypothesis_helpers import number_helpers as nh
from .globals import TestData
from . import test_parameter_flags as pf
from ivy_tests.test_ivy.helpers.test_parameter_flags import (
    BuiltInstanceStrategy,
    BuiltAsVariableStrategy,
    BuiltNativeArrayStrategy,
    BuiltGradientStrategy,
    BuiltContainerStrategy,
    BuiltWithOutStrategy,
    BuiltInplaceStrategy,
)
from ivy_tests.test_ivy.helpers.structs import FrontendMethodData
from ivy_tests.test_ivy.helpers.available_frameworks import (
    available_frameworks,
    ground_truth,
)

ground_truth = ground_truth()


cmd_line_args = (
    "with_out",
    "instance_method",
    "test_gradients",
)
cmd_line_args_lists = (
    "as_variable",
    "native_array",
    "container",
)


@st.composite
def num_positional_args_method(draw, *, method):
    """
    Draws an integers randomly from the minimum and maximum number of positional
    arguments a given method can take.

    Parameters
    ----------
    draw
        special function that draws data randomly (but is reproducible) from a given
        data-set (ex. list).
    method
        callable method

    Returns
    -------
    A strategy that can be used in the @given hypothesis decorator.
    """
    total, num_positional_only, num_keyword_only, = (
        0,
        0,
        0,
    )
    for param in inspect.signature(method).parameters.values():
        if param.name == "self":
            continue
        total += 1
        if param.kind == param.POSITIONAL_ONLY:
            num_positional_only += 1
        elif param.kind == param.KEYWORD_ONLY:
            num_keyword_only += 1
        elif param.kind == param.VAR_KEYWORD:
            num_keyword_only += 1
    return draw(
        nh.ints(min_value=num_positional_only, max_value=(total - num_keyword_only))
    )


@st.composite
def num_positional_args(draw, *, fn_name: str = None):
    """
    Draws an integers randomly from the minimum and maximum number of positional
    arguments a given function can take.

    Parameters
    ----------
    draw
        special function that draws data randomly (but is reproducible) from a
        given data-set (ex. list).
    fn_name
        name of the function.

    Returns
    -------
    A strategy that can be used in the @given hypothesis decorator.

    Examples
    --------
    @given(
        num_positional_args=num_positional_args(fn_name="floor_divide")
    )
    @given(
        num_positional_args=num_positional_args(fn_name="add")
    )
    """
    num_positional_only = 0
    num_keyword_only = 0
    total = 0
    fn = None
    for i, fn_name_key in enumerate(fn_name.split(".")):
        if i == 0:
            fn = ivy.__dict__[fn_name_key]
        else:
            fn = fn.__dict__[fn_name_key]
    for param in inspect.signature(fn).parameters.values():
        if param.name == "self":
            continue
        total += 1
        if param.kind == param.POSITIONAL_ONLY:
            num_positional_only += 1
        elif param.kind == param.KEYWORD_ONLY:
            num_keyword_only += 1
        elif param.kind == param.VAR_KEYWORD:
            num_keyword_only += 1
    return draw(
        nh.ints(min_value=num_positional_only, max_value=(total - num_keyword_only))
    )


# Decorators helpers


def _import_fn(fn_tree: str):
    """
    Imports a function from function tree string
    Parameters
    ----------
    fn_tree
        Full function tree without "ivy" root
        example: "functional.backends.jax.creation.arange".

    Returns
    -------
    Returns fn_name, imported module, callable function
    """
    split_index = fn_tree.rfind(".")
    fn_name = fn_tree[split_index + 1 :]
    module_to_import = fn_tree[:split_index]
    mod = importlib.import_module(module_to_import)
    callable_fn = mod.__dict__[fn_name]
    return callable_fn, fn_name, module_to_import


def _get_method_supported_devices_dtypes(
    method_name: str, class_module: str, class_name: str
):
    """
    Get supported devices and data types for a method in Ivy API
    Parameters
    ----------
    method_name
        Name of the method in the class

    class_module
        Name of the class module

    class_name
        Name of the class

    Returns
    -------
    Returns a dictonary containing supported device types and its supported data types
    for the method
    """
    supported_device_dtypes = {}
    backends = available_frameworks()
    for b in backends:  # ToDo can optimize this ?
        ivy.set_backend(b)
        _fn = getattr(class_module.__dict__[class_name], method_name)
        supported_device_dtypes[b] = ivy.function_supported_devices_and_dtypes(_fn)
        ivy.unset_backend()
    return supported_device_dtypes


def _get_supported_devices_dtypes(fn_name: str, fn_module: str):
    """
    Get supported devices and data types for a function in Ivy API
    Parameters
    ----------
    fn_name
        Name of the function

    fn_module
        Full import path of the function module

    Returns
    -------
    Returns a dictonary containing supported device types and its supported data types
    for the function
    """
    supported_device_dtypes = {}
    backends = available_frameworks()
    for b in backends:  # ToDo can optimize this ?

        ivy.set_backend(b)
        _tmp_mod = importlib.import_module(fn_module)
        _fn = _tmp_mod.__dict__[fn_name]
        supported_device_dtypes[b] = ivy.function_supported_devices_and_dtypes(_fn)
        ivy.unset_backend()
    return supported_device_dtypes


# Decorators


def handle_test(
    *,
    fn_tree: str,
    ground_truth_backend: str = ground_truth,
    number_positional_args=None,
    test_instance_method=BuiltInstanceStrategy,
    test_with_out=BuiltWithOutStrategy,
    test_gradients=BuiltGradientStrategy,
    as_variable_flags=BuiltAsVariableStrategy,
    native_array_flags=BuiltNativeArrayStrategy,
    container_flags=BuiltContainerStrategy,
    **_given_kwargs,
):
    """
    A test wrapper for Ivy functions.
    Sets the required test globals and creates test flags strategies.

    Parameters
    ----------
    fn_tree
        Full function import path

    ground_truth_backend
        The framework to assert test results are equal to

    number_positional_args
        A search strategy for determining the number of positional arguments to be
        passed to the function

    test_instance_method
        A search strategy that generates a boolean to test instance methods

    test_with_out
        A search strategy that generates a boolean to test the function with an `out`
        parameter

    test_gradients
        A search strategy that generates a boolean to test the function with arrays as
        gradients

    as_variable_flags
        A search strategy that generates a list of boolean flags for array inputs to be
        passed as a Variable array

    native_array_flags
        A search strategy that generates a list of boolean flags for array inputs to be
        passed as a native array

    container_flags
        A search strategy that generates a list of boolean flags for array inputs to be
        passed as a Container
    """
    fn_tree = "ivy." + fn_tree
    is_hypothesis_test = len(_given_kwargs) != 0

    if is_hypothesis_test:
        # Use the default strategy
        if number_positional_args is None:
            number_positional_args = num_positional_args(fn_name=fn_tree)
        # Generate the test flags strategy
        test_flags = pf.function_flags(
            num_positional_args=number_positional_args,
            instance_method=test_instance_method,
            with_out=test_with_out,
            test_gradients=test_gradients,
            as_variable=as_variable_flags,
            native_arrays=native_array_flags,
            container_flags=container_flags,
        )

    def test_wrapper(test_fn):
        callable_fn, fn_name, fn_mod = _import_fn(fn_tree)
        supported_device_dtypes = _get_supported_devices_dtypes(fn_name, fn_mod)

        # If a test is not a Hypothesis test, we only set the test global data
        if is_hypothesis_test:
            param_names = inspect.signature(test_fn).parameters.keys()
            # Check if these arguments are being asked for
            possible_arguments = {
                "test_flags": test_flags,
                "fn_name": st.just(fn_name),
                "ground_truth_backend": st.just(ground_truth_backend),
            }
            filtered_args = set(param_names).intersection(possible_arguments.keys())
            for key in filtered_args:
                _given_kwargs[key] = possible_arguments[key]
            # Wrap the test with the @given decorator
            wrapped_test = given(**_given_kwargs)(test_fn)
        else:
            wrapped_test = test_fn

        # Set the test data to be used by test helpers
        wrapped_test.test_data = TestData(
            test_fn=wrapped_test,
            fn_tree=fn_tree,
            fn_name=fn_name,
            supported_device_dtypes=supported_device_dtypes,
        )
        wrapped_test.ground_truth_backend = ground_truth_backend

        return wrapped_test

    return test_wrapper


def handle_frontend_test(
    *,
    fn_tree: str,
    aliases: List[str] = None,
    number_positional_args=None,
    test_with_out=BuiltWithOutStrategy,
    test_inplace=BuiltInplaceStrategy,
    as_variable_flags=BuiltAsVariableStrategy,
    native_array_flags=BuiltNativeArrayStrategy,
    **_given_kwargs,
):
    """
    A test wrapper for Ivy frontend functions.
    Sets the required test globals and creates test flags strategies.

    Parameters
    ----------
    fn_tree
        Full function import path

    number_positional_args
        A search strategy for determining the number of positional arguments to be
        passed to the function

    test_inplace
        A search strategy that generates a boolean to test the method with `inplace`
        update

    test_with_out
        A search strategy that generates a boolean to test the function with an `out`
        parameter

    as_variable_flags
        A search strategy that generates a list of boolean flags for array inputs to be
        passed as a Variable array

    native_array_flags
        A search strategy that generates a list of boolean flags for array inputs to be
        passed as a native array
    """
    fn_tree = "ivy.functional.frontends." + fn_tree
    if aliases is not None:
        for i in range(len(aliases)):
            aliases[i] = "ivy.functional.frontends." + aliases[i]
    is_hypothesis_test = len(_given_kwargs) != 0

    if is_hypothesis_test:
        # Use the default strategy
        if number_positional_args is None:
            number_positional_args = num_positional_args(fn_name=fn_tree)
        # Generate the test flags strategy
        test_flags = pf.frontend_function_flags(
            num_positional_args=number_positional_args,
            with_out=test_with_out,
            inplace=test_inplace,
            as_variable=as_variable_flags,
            native_arrays=native_array_flags,
        )

    def test_wrapper(test_fn):
        callable_fn, fn_name, fn_mod = _import_fn(fn_tree)
        supported_device_dtypes = _get_supported_devices_dtypes(fn_name, fn_mod)

        # If a test is not a Hypothesis test, we only set the test global data
        if is_hypothesis_test:
            param_names = inspect.signature(test_fn).parameters.keys()
            # Check if these arguments are being asked for
            possible_arguments = {
                "test_flags": test_flags,
                "fn_tree": st.sampled_from([fn_tree] + aliases)
                if aliases is not None
                else st.just(fn_tree),
            }
            filtered_args = set(param_names).intersection(possible_arguments.keys())
            for key in filtered_args:
                # extend Hypothesis given kwargs with our stratigies
                _given_kwargs[key] = possible_arguments[key]
            # Wrap the test with the @given decorator
            wrapped_test = given(**_given_kwargs)(test_fn)
        else:
            wrapped_test = test_fn

        wrapped_test.test_data = TestData(
            test_fn=wrapped_test,
            fn_tree=fn_tree,
            fn_name=fn_name,
            supported_device_dtypes=supported_device_dtypes,
        )

        return wrapped_test

    return test_wrapper


def _import_method(method_tree: str):
    split_index = method_tree.rfind(".")
    class_tree, method_name = method_tree[:split_index], method_tree[split_index + 1 :]
    split_index = class_tree.rfind(".")
    mod_to_import, class_name = class_tree[:split_index], class_tree[split_index + 1 :]
    _mod = importlib.import_module(mod_to_import)
    _class = _mod.__getattribute__(class_name)
    _method = getattr(_class, method_name)
    return _method, method_name, _class, class_name, _mod


def handle_method(
    *, method_tree, ground_truth_backend: str = ground_truth, **_given_kwargs
):
    """
    A test wrapper for Ivy methods.
    Sets the required test globals and creates test flags strategies.

    Parameters
    ----------
    method_tree
        Full method import path

    ground_truth_backend
        The framework to assert test results are equal to
    """
    method_tree = "ivy." + method_tree
    is_hypothesis_test = len(_given_kwargs) != 0

    def test_wrapper(test_fn):
        callable_method, method_name, class_, class_name, method_mod = _import_method(
            method_tree
        )
        supported_device_dtypes = _get_method_supported_devices_dtypes(
            method_name, method_mod, class_name
        )

        if is_hypothesis_test:
            fn_args = typing.get_type_hints(test_fn)
            param_names = inspect.signature(test_fn).parameters.keys()

            for k, v in fn_args.items():
                if (
                    v is pf.NativeArrayFlags
                    or v is pf.ContainerFlags
                    or v is pf.AsVariableFlags
                ):
                    _given_kwargs[k] = st.lists(st.booleans(), min_size=1, max_size=1)
                elif v is pf.NumPositionalArg:
                    if k.startswith("method"):
                        _given_kwargs[k] = num_positional_args(
                            fn_name=f"{class_name}.{method_name}"
                        )
                    else:
                        _given_kwargs[k] = num_positional_args(
                            fn_name=class_name + ".__init__"
                        )
                elif v is pf.BuiltGradientStrategy:
                    _given_kwargs[k] = v
            possible_arguments = {
                "class_name": st.just(class_name),
                "method_name": st.just(method_name),
                "ground_truth_backend": st.just(ground_truth_backend),
            }
            filtered_args = set(param_names).intersection(possible_arguments.keys())
            for key in filtered_args:
                _given_kwargs[key] = possible_arguments[key]
            wrapped_test = given(**_given_kwargs)(test_fn)
        else:
            wrapped_test = test_fn

        wrapped_test.test_data = TestData(
            test_fn=wrapped_test,
            fn_tree=method_tree,
            fn_name=method_name,
            supported_device_dtypes=supported_device_dtypes,
        )
        wrapped_test.ground_truth_backend = ground_truth_backend

        return wrapped_test

    return test_wrapper


def handle_frontend_method(
    *, class_tree: str, init_tree: str, method_name: str, **_given_kwargs
):
    """
    A test wrapper for Ivy frontends methods.
    Sets the required test globals and creates test flags strategies.

    Parameters
    ----------
    class_tree
        Full class import path

    init_tree
        Full import path for the function used to create the class

    method_name
        Name of the method
    """
    split_index = init_tree.rfind(".")
    framework_init_module = init_tree[:split_index]
    ivy_init_module = f"ivy.functional.frontends.{init_tree[:split_index]}"
    init_name = init_tree[split_index + 1 :]
    init_tree = f"ivy.functional.frontends.{init_tree}"
    is_hypothesis_test = len(_given_kwargs) != 0

    def test_wrapper(test_fn):
        split_index = class_tree.rfind(".")
        class_module_path, class_name = (
            class_tree[:split_index],
            class_tree[split_index + 1 :],
        )
        class_module = importlib.import_module(class_module_path)

        method_class = getattr(class_module, class_name)
        callable_method = getattr(method_class, method_name)
        supported_device_dtypes = _get_method_supported_devices_dtypes(
            method_name, class_module, class_name
        )

        if is_hypothesis_test:
            param_names = inspect.signature(test_fn).parameters.keys()
            fn_args = typing.get_type_hints(test_fn)

            for k, v in fn_args.items():
                if (
                    v is pf.NativeArrayFlags
                    or v is pf.ContainerFlags
                    or v is pf.AsVariableFlags
                ):
                    _given_kwargs[k] = st.lists(st.booleans(), min_size=1, max_size=1)
                elif v is pf.NumPositionalArgMethod:
                    _given_kwargs[k] = num_positional_args_method(
                        method=callable_method
                    )
                # TODO temporay, should also handle if the init is a method.
                elif v is pf.NumPositionalArgFn:
                    _given_kwargs[k] = num_positional_args(fn_name=init_tree[4:])

            frontend_helper_data = FrontendMethodData(
                ivy_init_module=importlib.import_module(ivy_init_module),
                framework_init_module=importlib.import_module(framework_init_module),
                init_name=init_name,
                method_name=method_name,
            )
            possible_arguments = {"frontend_method_data": st.just(frontend_helper_data)}
            filtered_args = set(param_names).intersection(possible_arguments.keys())
            for key in filtered_args:
                _given_kwargs[key] = possible_arguments[key]
            wrapped_test = given(**_given_kwargs)(test_fn)
        else:
            wrapped_test = test_fn

        wrapped_test.test_data = TestData(
            test_fn=wrapped_test,
            fn_tree=f"{init_tree}.{method_name}",
            fn_name=method_name,
            supported_device_dtypes=supported_device_dtypes,
        )

        return wrapped_test

    return test_wrapper


@st.composite
def seed(draw):
    return draw(st.integers(min_value=0, max_value=2**8 - 1))
