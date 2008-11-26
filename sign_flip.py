from numpy import *

def sign_flip_svd(x):
    """Implementation of sign corrected svd.
    http://csmr.ca.sandia.gov/~tgkolda/pubs/SAND2007-6422.pdf
    """
    
    u,s,v = linalg.svd(x, full_matrices=False)
    #u = matrix(u)
    #v = matrix(v)
    #y = matrix(x)
    y = x

    sleft = [sum(ss(dot(u[:,k].T, y[:,j]))
                 for j in range(y.shape[1]))
             for k in range(u.shape[1])]
    sright = [sum(ss(dot(v[k,:], y[i,:].T))
                  for i in range(y.shape[0]))
              for k in range(v.shape[0])]

    for k in range(u.shape[1]):
        if sleft[k] < 0 and sright[k] < 0:
            u[:,k] = -u[:,k]
            v[k,:] = -v[k,:]
    return u,s,v

def ss(d):
    "Return the signed square of d."
    return sign(d)*d**2
