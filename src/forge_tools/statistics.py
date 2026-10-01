"""Bounded statistics: explicit contracts replace broken legacy wrappers."""
import itertools, math,functools
import numpy as np
from scipy import stats

def finite_result(function):
    @functools.wraps(function)
    def checked(*args,**kwargs):
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            result=function(*args,**kwargs)
        def visit(value):
            if isinstance(value,float) and not math.isfinite(value):raise ValueError('nonfinite_computation_rejected')
            if isinstance(value,dict):
                for item in value.values():visit(item)
            if isinstance(value,(list,tuple)):
                for item in value:visit(item)
        visit(result);return result
    return checked

def sample(values, minimum=2):
    if not isinstance(values,(list,tuple)) or not minimum <= len(values) <= 100000:
        raise ValueError("invalid_sample_size")
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in values):
        raise ValueError("finite_numeric_samples_required")
    return np.asarray(values,dtype=float)

@finite_result
def welch_ttest(a,b,alpha=0.05):
    if not isinstance(alpha,(int,float)) or isinstance(alpha,bool) or not 0<alpha<1: raise ValueError("invalid_alpha")
    a,b=sample(a),sample(b)
    va,vb=float(a.var(ddof=1)),float(b.var(ddof=1));sa,sb=va/len(a),vb/len(b)
    se=math.sqrt(sa+sb)
    if se==0: raise ValueError("zero_variance_ttest_undefined")
    df=(sa+sb)**2/(sa**2/(len(a)-1)+sb**2/(len(b)-1))
    difference=float(a.mean()-b.mean());t=difference/se;critical=float(stats.t.ppf(1-alpha/2,df))
    return {"method":"Welch","difference":difference,"t":t,"df":df,"p_two_sided":float(2*stats.t.sf(abs(t),df)),"ci":[difference-critical*se,difference+critical*se],"alpha":alpha,"assumptions":["independent_observations","independent_groups","appropriate_sampling_distribution"]}

@finite_result
def anova_oneway(groups):
    if not isinstance(groups,list) or not 2<=len(groups)<=32: raise ValueError("two_to_32_groups_required")
    arrays=[sample(g) for g in groups]
    if any(float(a.var(ddof=1))==0 for a in arrays): raise ValueError("nonzero_within_group_variance_required")
    f,p=stats.f_oneway(*arrays)
    return {"method":"one_way_classical_anova","f":float(f),"p":float(p),"df_between":len(arrays)-1,"df_within":sum(map(len,arrays))-len(arrays),"assumptions":["independent_samples","normal_residuals","equal_variances"]}

@finite_result
def linear_regression(x,y):
    y=sample(y,3)
    if not isinstance(x,list) or len(x)!=len(y) or not all(isinstance(row,list) for row in x): raise ValueError("X_requires_rows_as_observations")
    columns=len(x[0])
    if not 1<=columns<=32 or any(len(row)!=columns for row in x): raise ValueError("invalid_predictor_shape")
    matrix=np.array([sample(row,1) for row in x]);design=np.column_stack([np.ones(len(y)),matrix])
    if len(y)<=design.shape[1] or np.linalg.matrix_rank(design)!=design.shape[1]: raise ValueError("insufficient_or_rank_deficient_design")
    coefficients=np.linalg.lstsq(design,y,rcond=None)[0];residual=y-design@coefficients;sst=float(np.sum((y-y.mean())**2));sse=float(residual@residual)
    return {"intercept":float(coefficients[0]),"coefficients":coefficients[1:].tolist(),"sse":sse,"r_squared":1-sse/sst if sst>0 else None,"residual_df":len(y)-design.shape[1],"assumptions":["linear_conditional_mean","independent_errors"],"limitations":["No causal interpretation or automatic extrapolation validity."]}

def factorial_design(factors):
    if not isinstance(factors,list) or not 1<=len(factors)<=8 or any(not isinstance(x,str) or not x for x in factors) or len(set(factors))!=len(factors): raise ValueError("unique_1_to_8_factor_names_required")
    return {"factors":factors,"coded_levels":[-1,1],"matrix":[list(x) for x in itertools.product((-1,1),repeat=len(factors))],"limitations":["Physical levels, randomization, blocking and replication must be specified by the experiment owner."]}

@finite_result
def spc_known_sigma(values, center, sigma):
    data=sample(values,1)
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in (center,sigma)) or sigma<=0: raise ValueError("finite_positive_baseline_sigma_required")
    low,high=center-3*sigma,center+3*sigma
    return {"center":center,"lcl":low,"ucl":high,"outside_3sigma_indices":[i for i,x in enumerate(data) if x<low or x>high],"assumptions":["known_stable_baseline_center_and_sigma","individual_independent_observations"],"limitations":["No estimated Xbar-R constants, no WECO multi-rule claim, not specification limits."]}
