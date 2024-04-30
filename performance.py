"""
Used to optimize performance
"""
import time


T = dict()

def update_T(name, t):
    if not T.get(name): T[name] = [0,0]
    c_t, c_ct = T[name]
    T.update({name: [c_t+t, c_ct+1]})

