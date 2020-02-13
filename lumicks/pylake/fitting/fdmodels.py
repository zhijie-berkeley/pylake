from .model import Model
from .parameters import Parameter
from .detail.derivative_manipulation import invert_function, invert_jacobian
from .model import Model, InverseModel
import numpy as np


def force_model(name, model_type):
    """Generate a force model.

    Parameters
    ----------
    name : str
        Name to identify the model by (e.g. "DNA"). This name gets prefixed to the non-shared parameters.
    model_type : str
        Specifies which model to return. Valid options are:
        - Marko_Siggia
            Margo Siggia's Worm-like Chain model with d as dependent parameter (useful for F < 10 pN).
        - WLC
            Odijk's Extensible Worm-Like Chain model with F as independent parameter (useful for 10 pN < F < 30 pN)
        - tWLC
            Twistable Worm-Like Chain model with F as independent parameter (useful for 10 pN < F)
        - FJC
            Freely Jointed Chain model with F as independent parameter
        - invWLC
            Inverted Extensible Worm-Like Chain model with d as independent parameter (useful for 10 pN < F < 30 pN)
        - invtWLC
            Inverted Twistable Worm-Like Chain model with d as independent parameter (useful for 10 pN < F)
        - invFJC
            Inverted Freely Joint Chain model with d as independent parameter
    """
    kT_default = Parameter(value=4.11, lb=0.0, ub=8.0, vary=False, shared=True, unit='pN*nm')
    Lp_default = Parameter(value=40.0, lb=0.0, ub=np.inf, unit='nm')
    Lc_default = Parameter(value=16.0, lb=0.0, ub=np.inf, unit='micron')
    St_default = Parameter(value=1500.0, lb=0.0, ub=np.inf, unit='pN')
    if model_type == "offset":
        return Model(name, offset_model, offset_model_jac, derivative=offset_model_derivative,
                     offset=Parameter(value=0.01, lb=0, ub=np.inf))
    if model_type == "Marko_Siggia":
        return Model(name, Marko_Siggia, Marko_Siggia_jac, derivative=Marko_Siggia_derivative,
                     kT=kT_default, Lp=Lp_default, Lc=Lc_default)
    if model_type == "WLC":
        return Model(name, WLC, WLC_jac, derivative=WLC_derivative,
                     kT=kT_default, Lp=Lp_default, Lc=Lc_default, St=St_default)
    elif model_type == "tWLC":
        return Model(name, tWLC, tWLC_jac, derivative=tWLC_derivative,
                     kT=kT_default, Lp=Lp_default, Lc=Lc_default, St=St_default,
                     Fc=Parameter(value=30.6, lb=0.0, ub=50000.0, unit="pN"),
                     C=Parameter(value=440.0, lb=0.0, ub=50000.0, unit="pN*nm**2"),
                     g0=Parameter(value=-637, lb=-50000.0, ub=50000.0, unit="pN*nm"),
                     g1=Parameter(value=17.0, lb=-50000.0, ub=50000.0, unit="nm"),
                     )
    elif model_type == "FJC":
        return Model(name, FJC, FJC_jac, derivative=FJC_derivative,
                     kT=kT_default, Lp=Lp_default, Lc=Lc_default, St=St_default)
    elif model_type == "invWLC":
        return Model(name, invWLC, invWLC_jac, derivative=invWLC_derivative,
                     kT=kT_default, Lp=Lp_default, Lc=Lc_default, St=St_default)
    elif model_type == "invtWLC":
        return Model(name, invtWLC, invtWLC_jac,
                     kT=kT_default, Lp=Lp_default, Lc=Lc_default, St=St_default,
                     Fc=Parameter(value=30.6, lb=0.0, ub=100.0, unit="pN"),
                     C=Parameter(value=440.0, lb=0.0, ub=50000.0, unit="pN*nm**2"),
                     g0=Parameter(value=-637, lb=-50000.0, ub=50000.0, unit="pN*nm"),
                     g1=Parameter(value=17.0, lb=-50000.0, ub=50000.0, unit="nm"),
                     )
    elif model_type == "invFJC":
        return InverseModel(force_model(name, "FJC"))
    else:
        raise ValueError(f"Invalid model {model_type} selected. Valid options are WLC, tWLC, FJC, invWLC, invtWLC, "
                         f"invFJC.")


def offset_model(x, offset):
    """Offset on the the model output."""
    return offset * np.ones(x.shape)


def offset_model_jac(x, offset):
    """Offset on the model output."""
    return np.ones((1, len(x)))


def offset_model_derivative(x, offset):
    """Offset on the model output."""
    return np.zeros(len(x))


def Marko_Siggia(d, Lp, Lc, kT):
    """
    Markov Siggia's Worm-like Chain model based on only entropic contributions. Valid for F < 10 pN).

    References:
        1. J. Marko, E. D. Siggia. Stretching dna., Macromolecules 28.26,
        8759-8770 (1995).
    """
    d_div_Lc = d / Lc
    return (kT/Lp) * .25 * (1.0-d_div_Lc)**(-2) + d_div_Lc - .25


def Marko_Siggia_jac(d, Lp, Lc, kT):
    d_div_Lc = d / Lc
    return np.vstack((-0.25 * kT / (Lp * Lp * (1.0 - d_div_Lc) ** 2),
                     -d_div_Lc / Lc - 0.5 * d * kT / (Lc ** 2 * Lp * (1.0 - d_div_Lc) ** 3),
                     0.25 / (Lp * (1.0 - d_div_Lc) ** 2)))


def Marko_Siggia_derivative(d, Lp, Lc, kT):
    return 1/Lc + 0.5*kT/(Lc*Lp*(1.0 - d/Lc)**3)


def WLC(F, Lp, Lc, St, kT = 4.11):
    """
    Odijk's Extensible Worm-like Chain model

    References:
      1. T. Odijk, Stiff Chains and Filaments under Tension, Macromolecules
         28, 7016-7018 (1995).
      2. M. D. Wang, H. Yin, R. Landick, J. Gelles, S. M. Block, Stretching
         DNA with optical tweezers., Biophysical journal 72, 1335-46 (1997).

    Parameters
    ----------
    F : array_like
        force [pN]
    Lp : float
        persistence length [nm]
    Lc : float
        contour length [um]
    St : float
        stretching modulus [pN]
    kT : float
        Boltzmann's constant times temperature (default = 4.11 [pN nm]) [pN nm]
    """
    return Lc * (1.0 - 1.0/2.0*np.sqrt(kT/(F*Lp)) + F/St)


def WLC_jac(F, Lp, Lc, St, kT=4.11):
    sqrt_term = np.sqrt(kT / (F * Lp))
    return np.vstack((0.25 * Lc * sqrt_term / Lp,
                     F / St - 0.5 * sqrt_term + 1.0,
                     -F * Lc / (St * St),
                     -0.25 * Lc * sqrt_term / kT))


def tWLC(F, Lp, Lc, St, C, g0, g1, Fc, kT=4.11):
    """
    Twistable Worm-like Chain model

    References:
       1. P. Gross et al., Quantifying how DNA stretches, melts and changes
          twist under tension, Nature Physics 7, 731-736 (2011).

    Parameters
    ----------
    F : array_like
        force [pN]
    Lp : float
        persistence length [nm]
    Lc : float
        contour length [um]
    St : float
        stretching modulus [pN]
    C : float
        twist rigidity [pN nm^2]
    g0 : float
        twist stretch coupling [pN Nm]
    g1 : float
        twist stretch coupling [nm]
    Fc : float
        critical force for twist stretch coupling [pN]
    kT : float
        Boltzmann's constant times temperature (default = 4.11 [pN nm]) [pN nm]
    """
    g = np.zeros(np.size(F))
    g[F < Fc] = g0 + g1 * Fc
    g[F >= Fc] = g0 + g1 * F[F >= Fc]

    return Lc * (1.0 - 1.0 / 2.0 * np.sqrt(kT / (F * Lp)) + (C / (-g * g + St * C)) * F)


def tWLC_jac(F, Lp, Lc, St, C, g0, g1, Fc, kT=4.11):
    x0 = 1.0 / Lp
    x1 = np.sqrt(kT * x0 / F)
    x2 = 0.25 * Lc * x1
    x3 = C * F
    x4 = C * St
    x5 = F > Fc
    x6 = F <= Fc
    x7 = F * x5 + Fc * x6
    x8 = g0 + g1 * x7
    x9 = x8 * x8
    x10 = x4 - x9
    x11 = 1.0 / x10
    x12 = x10 ** (-2)
    x13 = 2.0 * Lc * x3
    x14 = 1.0 / x8
    x15 = x11 * x11

    return np.vstack((x0 * x2,
                      -0.5 * x1 + x11 * x3 + 1.0,
                      -C * C * F * Lc * x12,
                      Lc * (F * x11 - F * x12 * x4),
                      x15 * x13 * x8,
                      x15 * x13 * x14 * x7 * x9,
                      g1 * x15 * x13 * x14 * x9 * x6,
                      -x2 / kT))

    # Not continuous derivatives were removed from the 8th parameter derivative:
    # Original derivative was: g1 * x11 ** 2 * x13 * x14 * x9 * (F * Derivative(x5, Fc) + Fc * Derivative(x6, Fc) + x6)


def coth(x):
    sol = np.ones(x.shape)
    mask = abs(x) < 500
    sol[mask] = np.cosh(x[mask]) / np.sinh(x[mask])  # Crude overflow protection, this limit approaches 1.0
    mask = abs(x) < -500
    sol[mask] = -1.0  # Crude overflow protection, this limit approaches -1.0
    return sol


def FJC(F, Lp, Lc, St, kT=4.11):
    """
    Freely-Jointed Chain

    References:
       1. S. B. Smith, Y. Cui, C. Bustamante, Overstretching B-DNA: The
          Elastic Response of Individual Double-Stranded and Single-Stranded
          DNA Molecules, Science 271, 795-799 (1996).
       2. M. D. Wang, H. Yin, R. Landick, J. Gelles, S. M. Block, Stretching
          DNA with optical tweezers., Biophysical journal 72, 1335-46 (1997).

    Parameters
    ----------
    F : array_like
        force [pN]
    Lp : float
        persistence length [nm]
    Lc : float
        contour length [um]
    St : float
        elastic modulus [pN]
    kT : float
        Boltzmann's constant times temperature (default = 4.11 [pN nm]) [pN nm]
    """
    return Lc * (coth(2.0 * F * Lp / kT) - kT / (2.0 * F * Lp)) * (1.0 + F/St)


def FJC_jac(F, Lp, Lc, St, kT=4.11):
    x0 = 0.5 / F
    x1 = 2.0 * F / kT
    x2 = Lp * x1
    x3 = np.zeros(x2.shape)
    x3[abs(x2) < 300] = np.sinh(x2[abs(x2) < 300]) ** (-2)
    x4 = F / St + 1.0
    x5 = Lc * x4
    x6 = x0 / Lp
    x7 = -kT * x6 + coth(x2)
    return np.vstack((x5 * (-x1 * x3 + kT * x0 / (Lp * Lp)),
                      x4 * x7,
                      -F * Lc * x7 / (St*St),
                      x5 * (2.0 * F * Lp * x3 / (kT*kT) - x6)))


def invWLC(distance, Lp, Lc, St, kT=4.11):
    """
    Inverted Odijk's Worm-like Chain model

    References:
      1. T. Odijk, Stiff Chains and Filaments under Tension, Macromolecules
         28, 7016-7018 (1995).
      2. M. D. Wang, H. Yin, R. Landick, J. Gelles, S. M. Block, Stretching
         DNA with optical tweezers., Biophysical journal 72, 1335-46 (1997).

    Parameters
    ----------
    d : array_like
        extension [um]
    Lp : float
        persistence length [nm]
    Lc : float
        contour length [um]
    St : float
        stretching modulus [pN]
    kT : float
        Boltzmann's constant times temperature (default = 4.11 [pN nm]) [pN nm]
    """
    #
    # In short, this model was analytically solved, since it is basically a cubic equation. There are some issues
    # with this inverted model. Its derivatives are not defined everywhere, as they contain divisions by zero in
    # specific places due to the cube roots involved. This was worked around by preventing the denominators in these
    # equations to go to zero by clamping them to a lower bound. This results in far better numerical behaviour than
    # even the finite difference approximations.
    #
    # Define:
    #   alpha = (distance/Lc) - 1.0
    #   beta = 1.0 / St
    #   gamma = kT / Lp
    #
    # This allows us to obtain simple polynomial coefficients for the Odijk model. We divide the polynomial by the
    # leading coefficient to make things simpler for us. This leads to the following equations:
    #
    #   denom = beta ** 2.0
    #   a = - (2.0 * alpha * beta) / denom = - 2.0 * alpha / beta
    #   b = alpha * alpha / denom = (alpha * alpha) / (beta * beta)
    #   c = - 0.25 * gamma / denom = - gamma / (4 * beta * beta)
    #
    # We can see now that parameterizing w.r.t. St is easier than b and define:
    alpha = (distance / Lc) - 1.0
    gamma = kT / Lp

    a = - 2.0 * alpha * St
    b = (alpha * alpha) * (St * St)
    c = - 0.25 * gamma * (St * St)

    # Convert the equation to a depressed cubic for p and q, which'll allow us to greatly simplify the equations
    p = b - a * a / 3.0
    q = 2 * a * a * a / 27.0 - a * b / 3.0 + c
    det = q*q/4.0 + p*p*p/27.0

    # The model changes behaviours when the discriminant equates to zero. From this point we need a different root
    # resolution mechanism.
    sol = np.zeros(det.shape)
    mask = det >= 0

    sqrt_det = np.sqrt(det[mask])
    t1 = -q[mask]*0.5 + sqrt_det
    t2 = -q[mask]*0.5 - sqrt_det
    sol[mask] = np.cbrt(t1) + np.cbrt(t2)

    sqrt_minus_p = np.sqrt(-p[np.logical_not(mask)])
    q_masked = q[np.logical_not(mask)]

    s = 2.0 / np.sqrt(3.0) * sqrt_minus_p * \
        np.cos((1.0/3.0) * np.arcsin(3.0 * np.sqrt(3.0) * q_masked / (2.0 * sqrt_minus_p**3)) + np.pi/6.0)

    sol[np.logical_not(mask)] = 2.0 / np.sqrt(3.0) * sqrt_minus_p * \
        np.cos((1.0/3.0) * np.arcsin(3.0 * np.sqrt(3.0) * q_masked / (2.0 * sqrt_minus_p**3)) + np.pi/6.0)

    return sol - a / 3.0


def calc_root1_invwlc(det, p, q, dp_da, dq_da, dq_db):
    # Calculate the first root for det < 0
    # Note that dp/dc = 0, dp_db = 1, dq_dc = 1

    # There are two regimes here that need to be treated separately. Determinant >=0 and < 0.
    sqrt_det = np.sqrt(det)
    t1 = (sqrt_det - 0.5 * q) ** (2 / 3)
    t2 = (-sqrt_det - 0.5 * q) ** (2 / 3)

    # Derivatives of cube roots are not defined everywhere.
    #
    # The derivatives go over the bit where the cube roots are non-differentiable in the region of the model where it
    # switches from entropic to enthalpic behaviour. Even the finite difference derivatives look terrible here.
    #
    # When we approach Lc, t2 tends to zero, which causes problems with the division later.
    t1[abs(t1) < 1e-5] = 1e-5
    t2[abs(t2) < 1e-5] = 1e-5

    # When the discriminant goes to zero however, it means there are now repeated roots.
    sqrt_det[abs(sqrt_det) < 1e-5] = 1e-5

    # Compute all the elements required to evaluate the chain rule
    dy_ddet = 1.0 / (6.0 * sqrt_det * t1) - 1.0 / (6.0 * sqrt_det * t2)
    dy_dq = -1.0 / (6.0 * t1) - 1.0 / (6.0 * t2)
    dy_da = -(1.0 / 3.0)

    ddet_dp = p * p / 9.0
    ddet_dq = 0.5 * q

    # Total derivatives, terms multiplied by zero are omitted. Terms that are one are also omitted.
    # dp_db = dq_dc = 1
    total_dy_da = dy_ddet * ddet_dp * dp_da + dy_ddet * ddet_dq * dq_da + dy_dq * dq_da + dy_da
    total_dy_db = dy_ddet * ddet_dp + dy_ddet * ddet_dq * dq_db + dy_dq * dq_db
    total_dy_dc = dy_ddet * ddet_dq + dy_dq

    return total_dy_da, total_dy_db, total_dy_dc


def calc_root3_invwlc(p, q, dp_da, dq_da, dq_db):
    # If we define:
    #   sqmp = sqrt(-p)
    #   F = 3 * sqrt(3) * q / (2 * sqmp**3 )
    #
    # Then the solution is:
    #   2 /sqrt(3) * sqmp * cos((1/3) * asin(F) + pi/6) - a / 3
    #
    # Note that dp/dc = 0, dp_db = 1, dq_dc = 1
    # The rest of this file is simply applying the chain rule.
    sqmp = np.sqrt(-p)
    F = 3.0 * np.sqrt(3.0) * q / (2.0 * sqmp ** 3)

    dF_dsqmp = -9 * np.sqrt(3) * q / (2 * sqmp ** 4)
    dF_dq = 3.0 * np.sqrt(3) / (2.0 * sqmp ** 3)
    dsqmp_dp = -1.0 / (2.0 * sqmp)

    arg = np.arcsin(F) / 3.0 + np.pi / 6.0
    dy_dsqmp = 2.0 * np.sqrt(3.0) * np.cos(arg) / 3.0
    dy_dF = -2.0 * np.sqrt(3.0) * sqmp * np.sin(arg) / (9.0 * np.sqrt(1.0 - F * F))
    dy_da = -1.0 / 3.0

    # Total derivatives
    total_dy_da = dy_dsqmp * dsqmp_dp * dp_da + \
        dy_dF * (dF_dsqmp * dsqmp_dp * dp_da + dF_dq * dq_da) + \
        dy_da
    total_dy_db = dy_dsqmp * dsqmp_dp + \
        dy_dF * (dF_dsqmp * dsqmp_dp + dF_dq * dq_db)
    total_dy_dc = dy_dF * dF_dq

    return total_dy_da, total_dy_db, total_dy_dc


def invwlc_root_derivatives(a, b, c):
    """Calculate the root derivatives of a cubic polynomial with respect to the polynomial coefficients.

    For a polynomial of the form:
        x**3 + a * x**2 + b * x + c = 0

    Note that this is not a general root-finding function, but tailored for use with the inverted WLC model. For det < 0
    it returns the derivatives of the first root. For det > 0 it returns the derivatives of the third root.
    """
    p = b - a * a / 3.0
    q = 2.0 * a * a * a / 27.0 - a * b / 3.0 + c
    det = q * q / 4.0 + p * p * p / 27.0

    # Determine derivatives of our transformation from polynomial coefficients to helper coordinates p and q
    dp_da = -2.0 * a / 3.0
    dq_da = 2.0 * a ** 2.0 / 9.0 - b / 3.0
    dq_db = -a / 3.0

    total_dy_da = np.zeros(det.shape)
    total_dy_db = np.zeros(det.shape)
    total_dy_dc = np.zeros(det.shape)

    mask = det > 0
    total_dy_da[mask], total_dy_db[mask], total_dy_dc[mask] = \
        calc_root1_invwlc(det[mask], p[mask], q[mask], dp_da[mask], dq_da[mask], dq_db[mask])

    nmask = np.logical_not(mask)
    total_dy_da[nmask], total_dy_db[nmask], total_dy_dc[nmask] = \
        calc_root3_invwlc(p[nmask], q[nmask], dp_da[nmask], dq_da[nmask], dq_db[nmask])

    return total_dy_da, total_dy_db, total_dy_dc


def invWLC_jac(distance, Lp, Lc, St, kT=4.11):
    alpha = (distance / Lc) - 1.0
    gamma = kT / Lp

    St_squared = St * St
    a = - 2.0 * alpha * St
    b = (alpha * alpha) * St_squared
    c = - 0.25 * gamma * St_squared

    total_dy_da, total_dy_db, total_dy_dc = invwlc_root_derivatives(a, b, c)

    # Map back to our output parameters
    da_dLc = 2.0 * St * distance / Lc ** 2
    da_dSt = - 2.0 * alpha
    db_dLc = -2.0 * St ** 2 * distance * alpha / Lc ** 2
    db_dSt = 2.0 * St * alpha ** 2
    dc_dLp = 0.25 * St_squared * kT / Lp ** 2
    dc_dSt = -0.5 * St * gamma
    dc_dkT = -0.25 * St_squared / Lp

    # Terms multiplied by zero are omitted. Terms that are one are also omitted.
    total_dy_dLp = total_dy_dc * dc_dLp
    total_dy_dLc = total_dy_da * da_dLc + total_dy_db * db_dLc
    total_dy_dSt = total_dy_da * da_dSt + total_dy_db * db_dSt + total_dy_dc * dc_dSt
    total_dy_dkT = total_dy_dc * dc_dkT

    return [total_dy_dLp, total_dy_dLc, total_dy_dSt, total_dy_dkT]


def invWLC_derivative(distance, Lp, Lc, St, kT = 4.11):
    alpha = (distance / Lc) - 1.0
    gamma = kT / Lp

    St_squared = St * St
    a = - 2.0 * alpha * St
    b = (alpha * alpha) * St_squared
    c = - 0.25 * gamma * St_squared

    total_dy_da, total_dy_db, _ = invwlc_root_derivatives(a, b, c)

    # Map back to our output parameters
    da_dd = -2.0 * St / Lc
    db_dd = 2 * St ** 2 * (-1.0 + distance / Lc) / Lc

    return total_dy_da * da_dd + total_dy_db * db_dd


def WLC_derivative(F, Lp, Lc, St, kT = 4.11):
    x0 = 1.0 / F
    return Lc * (0.25 * x0 * np.sqrt(kT * x0 / Lp) + 1.0 / St)


def tWLC_derivative(F, Lp, Lc, St, C, g0, g1, Fc, kT):
    """Derivative of the tWLC model w.r.t. the independent variable"""
    x0 = 1.0 / F
    x1 = F > Fc
    x2 = F <= Fc
    x3 = g0 + g1 * (F * x1 + Fc * x2)
    x4 = x3 * x3
    x5 = 1.0 / (C * St - x4)

    # The derivative terms were omitted since they are incompatible with a smooth optimization algorithm.
    # Lc * (2.0 * C * F * g1 * x4 * x5 * x5 * (F * Derivative(x1, F) + Fc * Derivative(x2, F) + x1) / x3 + C * x5 + 0.25 * x0 * sqrt(kT * x0 / Lp))]
    return Lc * (2.0 * C * F * g1 * x4 * x5 * x5 * x1 / x3 + C * x5 + 0.25 * x0 * np.sqrt(kT * x0 / Lp))


def FJC_derivative(F, Lp, Lc, St, kT=4.11):
    """Derivative of the FJC model w.r.t. the independent variable"""
    x0 = 1.0/St
    x1 = 2.0*Lp/kT
    x2 = F*x1
    x3 = 0.5*kT/Lp

    # Overflow protection
    sinh_term = np.zeros(x2.shape)
    sinh_term[x2 < 300] = 1.0/np.sinh(x2[x2 < 300])**2

    return Lc*x0*(coth(x2) - x3/F) + Lc*(F*x0 + 1.0)*(-x1*sinh_term + x3/F**2)


def invtWLC(d, Lp, Lc, St, C, g0, g1, Fc, kT=4.11):
    """
    Inverted Twistable Worm-like Chain model

    References:
       1. P. Gross et al., Quantifying how DNA stretches, melts and changes
          twist under tension, Nature Physics 7, 731-736 (2011).

    Parameters
    ----------
    d : array_like
        distance [um]
    Lp : float
        persistence length [nm]
    Lc : float
        contour length [um]
    St : float
        stretching modulus [pN]
    C : float
        twist rigidity [pN nm^2]
    g0 : float
        twist stretch coupling [pN Nm]
    g1 : float
        twist stretch coupling [nm]
    Fc : float
        critical force for twist stretch coupling [pN]
    kT : float
        Boltzmann's constant times temperature (default = 4.11) [pN nm]
    """
    f_min = 0
    f_max = (-g0 + np.sqrt(St * C)) / g1  # Above this force the model loses its validity

    return invert_function(d, np.ones(d.shape), f_min, f_max,
                           lambda f_trial: tWLC(f_trial, Lp, Lc, St, C, g0, g1, Fc, kT),
                           lambda f_trial: tWLC_derivative(f_trial, Lp, Lc, St, C, g0, g1, Fc, kT))


def invtWLC_jac(d, Lp, Lc, St, C, g0, g1, Fc, kT=4.11):
    return invert_jacobian(d,
                           lambda f_trial: invtWLC(f_trial, Lp, Lc, St, C, g0, g1, Fc, kT),
                           lambda f_trial: tWLC_jac(f_trial, Lp, Lc, St, C, g0, g1, Fc, kT),
                           lambda f_trial: tWLC_derivative(f_trial, Lp, Lc, St, C, g0, g1, Fc, kT))


def invFJC(d, Lp, Lc, St, kT=4.11):
    """
    Inverted Freely-Jointed Chain

    References:
       1. S. B. Smith, Y. Cui, C. Bustamante, Overstretching B-DNA: The
          Elastic Response of Individual Double-Stranded and Single-Stranded
          DNA Molecules, Science 271, 795-799 (1996).
       2. M. D. Wang, H. Yin, R. Landick, J. Gelles, S. M. Block, Stretching
          DNA with optical tweezers., Biophysical journal 72, 1335-46 (1997).

    Parameters
    ----------
    d : array_like
        distance [um]
    Lp : float
        persistence length [nm]
    Lc : float
        contour length [um]
    St : float
        elastic modulus [pN]
    kT : float
        Boltzmann's constant times temperature (default = 4.11 [pN nm]) [pN nm]
    """
    f_min = 0
    f_max = np.inf  # Above this force the model loses its validity

    return invert_function(d, np.ones(d.shape), f_min, f_max,
                           lambda f_trial: FJC(f_trial, Lp, Lc, St, kT),
                           lambda f_trial: FJC_derivative(f_trial, Lp, Lc, St, kT))


def invFJC_jac(d, Lp, Lc, St, kT=4.11):
    return invert_jacobian(d,
                           lambda f_trial: invFJC(f_trial, Lp, Lc, St, kT),
                           lambda f_trial: FJC_jac(f_trial, Lp, Lc, St, kT),
                           lambda f_trial: FJC_derivative(f_trial, Lp, Lc, St, kT))