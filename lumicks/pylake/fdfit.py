import inspect
import numpy as np
import scipy as sp
from .detail.utilities import unique, unique_idx
from collections import OrderedDict
from copy import deepcopy
import scipy.optimize as optim
from itertools import chain


def parse_transformation(parameters, **kwargs):
    transformed = OrderedDict(zip(parameters, parameters))

    for key, value in kwargs.items():
        if key in transformed:
            transformed[key] = value
        else:
            raise KeyError(f"Parameter {key} to be substituted not found in model.")

    return transformed


def _generate_conditions(data_sets, parameter_lookup, model_parameters):
    """
    This function builds a list of unique conditions from a list of data sets and a list of index lists which link back
    the individual data fields to their simulation conditions.

    Parameters
    ----------
    data_sets : list of Data
        References to data
    parameter_lookup: OrderedDict[str, int]
        Lookup table for looking up parameter indices by name
    model_parameters: list of str
        Base model parameter names
    """
    # Quickly concatenate the parameter transformations corresponding to this condition
    str_conditions = []
    for data_set in data_sets:
        str_conditions.append(data_set.condition_string)

        assert set(data_set.transformations.keys()) == set(model_parameters), \
            "Source parameters in data parameter transformations are incompatible with the specified model parameters."

        assert set(data_set.transformations.values()).issubset(parameter_lookup.keys()), \
            "Parameter transformations contain transformed parameter names that are not in the combined parameter list."

    # Determine unique parameter conditions and the indices to get the appropriate unique condition from data index.
    unique_condition_strings, indices = unique_idx(str_conditions)
    indices = np.array(indices)

    data_link = []
    for condition_idx in np.arange(len(unique_condition_strings)):
        data_indices, = np.nonzero(np.equal(indices, condition_idx))
        data_link.append(data_indices)

    conditions = []
    for idx in data_link:
        transformations = data_sets[idx[0]].transformations
        conditions.append(Condition(transformations, parameter_lookup))

    return conditions, data_link


def invert_function(d, initial, f_min, f_max, model_function, derivative_function=None):
    """This function inverts a function using a least squares optimizer. For models where this is required, this is the
    most time consuming step.

    Parameters
    ----------
    d : array_like
        old independent parameter
    initial : array_like
        initial guess for the optimization procedure
    f_min : float
        minimum bound for inverted parameter
    f_max : float
        maximum bound for inverted parameter
    model_function : callable
        non-inverted model function
    derivative_function : callable
        model derivative with respect to the independent variable (returns an element per data point)
    """
    def jacobian(f_trial):
        return sp.sparse.diags(derivative_function(f_trial), offsets=0)

    jac = jacobian if derivative_function else "2-point"

    result = optim.least_squares(lambda f_trial: model_function(f_trial) - d, initial, jac=jac,
                                 jac_sparsity=sp.sparse.identity(len(d)),
                                 bounds=(f_min, f_max), method='trf', ftol=1e-06, xtol=1e-06, gtol=1e-6)

    return result.x


def invert_jacobian(d, inverted_model_function, jacobian_function, derivative_function):
    """This function computes the jacobian of the model when the model has been inverted with respect to the independent
    variable.

    The Jacobian of the function with one variable inverted is related to the original Jacobian
    The transformation Jacobian is structured as follows:

    [  dy/dF   dy/db   dy/dc  ]
    [   0        1       0    ]
    [   0        0       1    ]

    The inverse of this Jacobian provides us with the actual parameters that we are interested in. It is given by:
    [ (dy/da)^-1  -(dy/db)(dy/dF)^-1    -(dy/dc)(dy/dF)^-1 ]
    [    0                1                     0          ]
    [    0                0                     1          ]

    Parameters
    ----------
    d : values for the old independent variable
    inverted_model_function : callable
        inverted model function (model with the dependent and independent variable exchanged)
    jacobian_function : callable
        derivatives of the non-inverted model
    derivative_function : callable
        derivative of the non-inverted model w.r.t. the independent variable
    """
    F = inverted_model_function(d)
    jacobian = jacobian_function(F)
    derivative = derivative_function(F)
    inverse = 1.0/derivative
    inverted_dyda = np.tile(inverse, (jacobian.shape[0], 1))
    jacobian = -jacobian * inverted_dyda

    return jacobian


class Model:
    def __init__(self, model_function, jacobian=None, derivative=None, **kwargs):
        self.model_function = model_function
        parameter_names = inspect.getfullargspec(model_function).args[1:]
        self._parameters = OrderedDict(zip(parameter_names, [None] * len(parameter_names)))

        for key, value in kwargs.items():
            if key in self._parameters:
                self._parameters[key] = value
            else:
                raise KeyError(f"Model does not contain parameter {key}")

        self._jacobian = jacobian
        self._derivative = derivative

    def __add__(self, other):
        """
        Add two model outputs to form a new model.

        Parameters
        ----------
        other: Model
        """

        return CompositeModel(self, other)

    @staticmethod
    def _sanitize_input_types(data, parameter_vector):
        data = np.array(data).astype(float)
        parameter_vector = np.array(parameter_vector).astype(float)
        return data, parameter_vector

    def __call__(self, data, parameter_vector):
        data, parameter_vector = self._sanitize_input_types(data, parameter_vector)
        return self.model_function(data, *parameter_vector)

    def get_default(self, key):
        from copy import deepcopy
        return deepcopy(self._parameters[key])

    def jacobian(self, independent, parameter_vector):
        if self.has_jacobian:
            independent, parameter_vector = self._sanitize_input_types(independent, parameter_vector)
            return self._jacobian(independent, *parameter_vector)
        else:
            raise RuntimeError("Jacobian was requested but not supplied in the model.")

    def derivative(self, independent, parameter_vector):
        independent, parameter_vector = self._sanitize_input_types(independent, parameter_vector)
        return self._derivative(independent, *parameter_vector)

    @property
    def has_jacobian(self):
        if self._jacobian:
            return True

    def numerical_jacobian(self, independent, parameter_vector, dx=1e-6):
        independent, parameter_vector = self._sanitize_input_types(independent, parameter_vector)

        finite_difference_jacobian = np.zeros((len(parameter_vector), len(independent)))
        for i in np.arange(len(parameter_vector)):
            parameters = np.copy(parameter_vector)
            parameters[i] = parameters[i] + dx
            up = self(independent, parameters)
            parameters[i] = parameters[i] - 2.0 * dx
            down = self(independent, parameters)
            finite_difference_jacobian[i, :] = (up - down) / (2.0*dx)

        return finite_difference_jacobian

    def verify_jacobian(self, independent, parameters, plot=False, verbose=True, **kwargs):
        if len(parameters) != len(self._parameters):
            raise ValueError("Parameter vector has invalid length. "
                             f"Expected: {len(self._parameters)}, got: {len(parameters)}.")

        independent, parameters = self._sanitize_input_types(independent, parameters)

        jacobian = self.jacobian(independent, parameters)
        numerical_jacobian = self.numerical_jacobian(independent, parameters)

        if plot:
            import matplotlib.pyplot as plt
            plt.subplot(2, 1, 1)
            l1 = plt.plot(independent, np.transpose(jacobian))
            l2 = plt.plot(independent, np.transpose(numerical_jacobian), '--')
            plt.legend([l1[0], l2[0]], ('Analytical', 'Numerical'))
            plt.subplot(2, 1, 2)
            plt.plot(independent, np.transpose(jacobian - numerical_jacobian))

        is_close = np.allclose(jacobian, numerical_jacobian, **kwargs)

        if not is_close:
            if verbose:
                maxima = np.max(jacobian - numerical_jacobian, axis=1)
                for i, v in enumerate(maxima):
                    print(f"Parameter {self.parameter_names[i]}({i}): {v}")

            raise RuntimeError('Numerical Jacobian did not pass.')

        return is_close

    @property
    def parameter_names(self):
        return [x for x in self._parameters.keys()]


class InverseModel(Model):
    def __init__(self, model):
        """
        Combine two model outputs to form a new model (addition).

        Parameters
        ----------
        model: Model
        """
        self.model = model

    def __call__(self, data, parameter_vector):
        f_min = -np.inf
        f_max = np.inf
        initial = np.ones(data.shape)

        return invert_function(data, initial, f_min, f_max,
                               lambda f_trial: self.model(f_trial, parameter_vector),  # Forward model
                               lambda f_trial: self.model.derivative(f_trial, parameter_vector))

    @property
    def has_jacobian(self):
        """Does the model have sufficient information to determine its inverse numerically?
        This requires a Jacobian and a derivative w.r.t. independent variable."""
        return True

    def jacobian(self, data, parameter_vector):
        return invert_jacobian(data,
                               lambda f_trial: self(f_trial, parameter_vector),  # Inverse model (me)
                               lambda f_trial: self.model.jacobian(f_trial, parameter_vector),
                               lambda f_trial: self.model.derivative(f_trial, parameter_vector))

    @property
    def _parameters(self):
        return self.model._parameters


class CompositeModel(Model):
    def __init__(self, lhs, rhs):
        """
        Combine two model outputs to form a new model (addition).

        Parameters
        ----------
        lhs: Model
        rhs: Model
        """
        self.lhs = lhs
        self.rhs = rhs

        self._parameters = OrderedDict()
        for i, v in self.lhs._parameters.items():
            self._parameters[i] = v
        for i, v in self.rhs._parameters.items():
            self._parameters[i] = v

        parameters_lhs = list(self.lhs._parameters.keys())
        parameters_rhs = list(self.rhs._parameters.keys())
        parameters_all = list(self._parameters.keys())

        self.lhs_parameters = [True if x in parameters_lhs else False for x in parameters_all]
        self.rhs_parameters = [True if x in parameters_rhs else False for x in parameters_all]

    def __call__(self, data, parameter_vector):
        return self.lhs(data, parameter_vector[self.lhs_parameters]) + \
            self.rhs(data, parameter_vector[self.rhs_parameters])

    @property
    def has_jacobian(self):
        return self.lhs.has_jacobian and self.rhs.has_jacobian

    def jacobian(self, data, parameter_vector):
        if self.has_jacobian:
            jacobian = np.zeros((len(parameter_vector), len(data)))
            jacobian[self.lhs_parameters, :] += self.lhs.jacobian(data, parameter_vector[self.lhs_parameters])
            jacobian[self.rhs_parameters, :] += self.rhs.jacobian(data, parameter_vector[self.rhs_parameters])

            return jacobian

    def derivative(self, data, parameter_vector):
        lhs_derivative = self.lhs.derivative(data, parameter_vector[self.lhs_parameters])
        rhs_derivative = self.rhs.derivative(data, parameter_vector[self.rhs_parameters])

        return lhs_derivative + rhs_derivative


class Parameter:
    def __init__(self, value=0.0, lb=-np.inf, ub=np.inf, vary=True, init=None):
        self.value = value
        self.lb = lb
        self.ub = ub
        self.vary = vary
        if init:
            self.init = init
        else:
            self.init = self.value

    def __repr__(self):
        return f"lumicks.pylake.fdfit.Parameter(value: {self.value}, lb: {self.lb}, ub: {self.ub})"

    def __str__(self):
        return self.__repr__()


class Parameters:
    def __init__(self):
        self._src = OrderedDict()

    def __iter__(self):
        return self._src.__iter__()

    def items(self):
        return self._src.items()

    def __getitem__(self, item):
        if isinstance(item, slice):
            raise IndexError("Slicing not supported. Only indexing.")

        if item in self._src:
            return self._src[item]

    def __setitem__(self, item, value):
        if item in self._src:
            self._src[item].value = value

    def __len__(self):
        return len(self._src)

    def __str__(self):
        return_str = ""
        for key, param in self._src.items():
            return_str = return_str + f"{key}      {param.value}\n"

        return return_str

    def set_parameters(self, parameters, defaults):
        """Rebuild the parameter vector. Note that this can potentially alter the parameter order if the strings are
        given in a different order.

        Parameters
        ----------
        parameters : list of str
            parameter names
        defaults : Parameter or None
            default parameter objects
        """
        new_parameters = OrderedDict(zip(parameters, [Parameter() if x is None else x for x in defaults]))
        for key, value in self._src.items():
            if key in new_parameters:
                new_parameters[key] = value

        self._src = new_parameters

    @property
    def keys(self):
        return np.array([key for key in self._src.keys()])

    @property
    def values(self):
        return np.array([param.value for param in self._src.values()])

    @property
    def fitted(self):
        return np.array([param.vary for param in self._src.values()])

    @property
    def lb(self):
        return np.array([param.lb for param in self._src.values()])

    @property
    def ub(self):
        return np.array([param.ub for param in self._src.values()])


class FitObject:
    """Object which is used for fitting. It is a collection of a model alongside its data.

    A fit object builds the linkages required to propagate parameters used in sub-models to a global parameter vector
    used by the optimization algorithm.
    """
    def __init__(self, model):
        self.model = model
        self._data = []
        self._conditions = []
        self._data_link = None
        self._parameters = Parameters()
        self._current_new_idx = 0

        self._invalidate_build()

    def load_data(self, x, y, **kwargs):
        self._invalidate_build()

        parameter_list = parse_transformation(self.model.parameter_names, **kwargs)
        self._data.append(Data(x, y, parameter_list))
        return self

    def _build_model(self):
        """This function generates the global parameter list from the parameters of the individual submodels.
        It also generates unique conditions from the data specification."""
        parameter_names = [name for data in self._data for name in data.parameter_names]

        unique_parameter_names = unique(parameter_names)
        parameter_lookup = OrderedDict(zip(unique_parameter_names, np.arange(len(unique_parameter_names))))

        defaults = [self.model.get_default(name) for data in self._data for name in data.source_parameter_names]
        defaults = [defaults[parameter_names.index(l)] for l in unique_parameter_names]

        self._conditions, self._data_link = _generate_conditions(self._data, parameter_lookup,
                                                                 self.model.parameter_names)
        self._parameters.set_parameters(unique_parameter_names, defaults)

    def _check_rebuild(self):
        """
        Checks whether the model state is up to date. Any user facing methods should ideally check whether the model
        needs to be rebuilt.
        """
        if not self._built:
            self._build_model()
            self._built = True

    def _invalidate_build(self):
        self._built = False

    @property
    def n_residuals(self):
        self._check_rebuild()
        count = 0
        for data in self._data:
            count += len(data.independent)

        return count

    @property
    def parameters(self):
        self._check_rebuild()
        return self._parameters

    @property
    def n_parameters(self):
        self._check_rebuild()
        return len(self._parameters)

    def plot_data(self, idx=None):
        import matplotlib.pyplot as plt

        for data_idx in idx if idx else np.arange(len(self._data)):
            data = self._data[data_idx]
            plt.plot(data.x, data.y, '.')

    def plot_model(self, idx=None):
        import matplotlib.pyplot as plt
        self._check_rebuild()

        def intersection(l1, l2):
            return [value for value in l1 if value in l2]

        if not idx:
            idx = np.arange(len(self._data))

        for condition, data_sets in zip(self._conditions, self._data_link):
            p_local = condition.get_local_parameters(self.parameters.values)
            [plt.plot(np.sort(self._data[value].x), self.model(np.sort(self._data[value].x), p_local))
             for value in idx if value in self._data_link]

    def fit(self, **kwargs):
        parameter_vector = self.parameters.values
        fitted = self.parameters.fitted
        lb = self.parameters.lb
        ub = self.parameters.ub

        def residual(parameters):
            parameter_vector[fitted] = parameters
            return self._calculate_residual(parameter_vector)

        def jacobian(parameters):
            parameter_vector[fitted] = parameters
            return self._evaluate_jacobian(parameter_vector)[:, fitted]

        result = optim.least_squares(residual, parameter_vector[fitted],
                                     jac=jacobian if self.model.has_jacobian else "2-point",
                                     bounds=(lb[fitted], ub[fitted]),
                                     method='trf', ftol=1e-06, xtol=1e-06, gtol=1e-8, **kwargs)

        parameter_names = self.parameters.keys
        parameter_vector[fitted] = result.x

        for name, value in zip(parameter_names, parameter_vector):
            self.parameters[name] = value

    def _calculate_residual(self, parameter_values=[]):
        self._check_rebuild()
        if len(parameter_values) == 0:
            parameter_values = self.parameters.values

        residual_idx = 0
        residual = np.zeros(self.n_residuals)
        for condition, data_sets in zip(self._conditions, self._data_link):
            p_local = condition.get_local_parameters(parameter_values)
            for data in data_sets:
                data_set = self._data[data]
                y_model = self.model(data_set.x, p_local)

                residual[residual_idx:residual_idx + len(y_model)] = data_set.y - y_model
                residual_idx += len(y_model)

        return residual

    def _evaluate_jacobian(self, parameter_values=[]):
        self._check_rebuild()
        if len(parameter_values) == 0:
            parameter_values = self.parameters.values

        residual_idx = 0
        jacobian = np.zeros((self.n_residuals, self.n_parameters))
        for condition, data_sets in zip(self._conditions, self._data_link):
            p_local = condition.get_local_parameters(parameter_values)
            p_indices = condition.p_indices
            for data in data_sets:
                data_set = self._data[data]
                sensitivities = np.transpose(self.model.jacobian(data_set.x, p_local))
                n_res = sensitivities.shape[0]

                jacobian[residual_idx:residual_idx + n_res, p_indices] = \
                    jacobian[residual_idx:residual_idx + n_res, p_indices] - sensitivities

                residual_idx += n_res

        return jacobian

    @property
    def sigma(self):
        """Error variance of the data points. Ideally, this will eventually depend on the exact error model used. For
        now, we use the a-posteriori variance estimate based on the residual."""
        res = self._calculate_residual()
        return np.sqrt(np.var(res)) * np.ones(len(res))

    @property
    def log_likelihood(self):
        res = self._calculate_residual()
        sigma = self.sigma
        return - (self.n_residuals/2.0) * np.log(2.0 * np.pi) - np.sum(np.log(sigma)) - sum((res/sigma)**2) / 2.0

    @property
    def aic(self):
        self._check_rebuild()
        k = sum(self.parameters.fitted)
        LL = self.log_likelihood
        return 2.0 * k - 2.0 * LL

    @property
    def aicc(self):
        aic = self.aic
        k = sum(self.parameters.fitted)
        return aic + (2.0 * k * k + 2.0 * k)/(self.n_residuals - k - 1.0)

    @property
    def bic(self):
        k = sum(self.parameters.fitted)
        return k * np.log(self.n_residuals) - 2.0 * self.log_likelihood

    @property
    def cov(self):
        """
        Returns the inverse of the approximate Hessian. This approximation is valid when the residuals of the fitting
        problem are small.
        """
        J = self._evaluate_jacobian()
        J = J / np.transpose(np.tile(self.sigma, (J.shape[1], 1)))
        return np.linalg.inv(np.transpose(J).dot(J))


class Data:
    def __init__(self, x, y, transformations):
        self.x = x
        self.y = y
        self.transformations = transformations

    @property
    def independent(self):
        return self.x

    @property
    def dependent(self):
        return self.y

    @property
    def condition_string(self):
        return '|'.join(str(x) for x in self.transformations.values())

    @property
    def parameter_names(self):
        """
        Parameter names for free parameters after transformation
        """
        return [x for x in self.transformations.values() if isinstance(x, str)]

    @property
    def source_parameter_names(self):
        """
        Parameter names for free parameters after transformation
        """
        return [x for x, y in self.transformations.items() if isinstance(y, str)]


class Condition:
    def __init__(self, transformations, global_dictionary):
        self.transformations = deepcopy(transformations)
        self.p_external = np.array([True if isinstance(x, str) else False for x in self.transformed])
        self.p_local = np.array([0.0 if isinstance(x, str) else x for x in self.transformed])
        self.p_reference = [x for x in self.transformed if isinstance(x, str)]
        self.p_indices = [global_dictionary[key] for key in self.p_reference]

    @property
    def transformed(self):
        return self.transformations.values()

    def get_local_parameters(self, par_global):
        self.p_local[self.p_external] = par_global[self.p_indices]
        return self.p_local
