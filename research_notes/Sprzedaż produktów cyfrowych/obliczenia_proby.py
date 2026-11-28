import math, random
from statistics import NormalDist
N=NormalDist()
def n_two(p1,rel,alpha=0.05,power=0.8):
    p2=p1*(1+rel); za=N.inv_cdf(1-alpha/2); zb=N.inv_cdf(power)
    pb=(p1+p2)/2
    return math.ceil((za*math.sqrt(2*pb*(1-pb))+zb*math.sqrt(p1*(1-p1)+p2*(1-p2)))**2/(p2-p1)**2)
print("A/B per-arm n (alpha .05 two-sided, power .8)")
for p in (0.01,0.02,0.03,0.05):
    print(p,[ (int(r*100),n_two(p,r)) for r in (0.2,0.3,0.5,1.0)])
def wilson(x,n,z=1.96):
    ph=x/n; d=1+z*z/n; c=(ph+z*z/(2*n))/d; h=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/d
    return round((c-h)*100,2),round((c+h)*100,2)
print("Wilson 95% CI")
for x,n in ((0,100),(2,100),(5,250),(10,500),(20,1000),(30,1000),(3,300),(0,300),(8,400)):
    print(x,n,wilson(x,n))
from math import comb
def binom_cdf(k,n,p):
    return sum(comb(n,i)*p**i*(1-p)**(n-i) for i in range(0,k+1))
print("Single-arm threshold design: H0 p<=p0 vs H1 p>=p1, one-sided alpha<=.10, power>=.80 (exact binomial)")
for p0,p1 in ((0.01,0.03),(0.01,0.02),(0.02,0.04),(0.02,0.05),(0.005,0.02),(0.03,0.06)):
    for n in range(20,20000,5):
        # find smallest critical c with P(X>=c|p0)<=alpha
        c=0
        while 1-binom_cdf(c-1,n,p0)>0.10: c+=1
        if 1-binom_cdf(c-1,n,p1)>=0.80:
            print(p0,p1,"n=",n,"go if conversions >=",c,"alpha=",round(1-binom_cdf(c-1,n,p0),3),"power=",round(1-binom_cdf(c-1,n,p1),3)); break
# peeking simulation
random.seed(1)
def peek(looks,n_per_arm=2000,p=0.03,sims=4000):
    fp=0
    step=n_per_arm//looks
    for _ in range(sims):
        a=b=0; hit=False
        for l in range(1,looks+1):
            a+=sum(1 for _ in range(step) if random.random()<p)
            b+=sum(1 for _ in range(step) if random.random()<p)
            n=l*step; pa=a/n; pb=b/n; pp=(a+b)/(2*n)
            se=math.sqrt(2*pp*(1-pp)/n) if 0<pp<1 else 0
            if se>0 and abs(pa-pb)/se>1.96: hit=True; break
        fp+=hit
    return fp/sims
print("Peeking A/A false positive rate (nominal 5%)")
for L in (1,2,5,10,20):
    print(L,round(peek(L),3))
# Bayesian beta posterior P(p>thr)
def post_prob(x,n,thr,a=1,b=1,draws=200000):
    c=0
    for _ in range(draws):
        if random.betavariate(a+x,b+n-x)>thr: c+=1
    return c/draws
print("Bayes P(p>thr) uniform prior")
for x,n,t in ((6,300,0.01),(3,300,0.01),(9,300,0.02),(12,500,0.015),(4,500,0.015),(1,300,0.01),(15,500,0.02)):
    print(x,n,t,round(post_prob(x,n,t),3))
