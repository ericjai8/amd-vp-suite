import sys, numpy as np, pandas as pd, matplotlib
sys.path.insert(0,'../../fast-pass-lab/lab')  # data loader from the fast-pass-lab repo
import data as D
matplotlib.use('Agg'); import matplotlib.pyplot as plt
df=D.load('5m'); S=D.enrich(df)
o,h,l,c,hm,tday=S['o'],S['h'],S['l'],S['c'],S['hm'],S['tday']
K,ERMAX,MINB,SLACK,ZONE,TOUCH,XPH,R2MAX=8.0,0.30,12,24,0.20,2,1.0,float(sys.argv[1])
def r2q(y):
    x=np.arange(len(y)); p=np.polyfit(x,y,2); res=y-np.polyval(p,x); tot=((y-y.mean())**2).sum()
    return 1-(res**2).sum()/tot if tot>0 else 0
def good(C,H,L,i,e):
    hh,ll=H[i:e+1].max(),L[i:e+1].min(); mid=(hh+ll)/2; n=e-i+1
    s=np.sign(C[i:e+1]-mid); s=s[s!=0]; cr=int((s[1:]!=s[:-1]).sum())
    pass
    p=np.abs(np.diff(C[i:e+1])).sum()
    if p<=0 or abs(C[e]-C[i])/p>ERMAX: return False
    return r2q(C[i:e+1]) <= R2MAX
def detect(ix):
    H,L,C=h[ix],l[ix],c[ix]; n=len(ix); best=(0,None)
    for e in range(n-1, max(1,n-1-SLACK)-1, -1):
        hh,ll=H[e],L[e]; rngs=[H[e]-L[e]]
        for i in range(e-1,-1,-1):
            nh,nl=max(hh,H[i]),min(ll,L[i]); rngs.append(H[i]-L[i]); med=np.median(rngs)
            if len(rngs)>=6 and med>0 and (nh-nl)/med>K: break
            hh,ll=nh,nl
            if e-i+1>best[0] and e-i+1>=MINB and good(C,H,L,i,e):
                best=(e-i+1,(i,e,hh,ll))
    if best[1] is None: return None,'none'
    i,e,hh,ll=best[1]
    # trim the lead-in: start where closes first enter the core (15th-85th percentile of the span's closes)
    q1,q2=np.percentile(C[i:e+1],[15,85])
    while i<e-MINB and not (q1<=C[i]<=q2): i+=1
    hh,ll=H[i:e+1].max(),L[i:e+1].min()
    z=(hh-ll)*ZONE; tH=tL=0; inH=inL=False
    for j in range(i,e+1):
        a=H[j]>=hh-z; b=L[j]<=ll+z
        tH+= a and not inH; tL+= b and not inL; inH,inL=a,b
    return best[1], ('ok' if tH>=TOUCH and tL>=TOUCH else 'edges')
days=pd.Series(np.arange(len(c))).groupby(tday)
res=[]; samples={}
for d,g in days:
    ix=g.to_numpy(); w=ix[(hm[ix]>=1800)|(hm[ix]<200)]
    if len(w)<40: continue
    fit,status=detect(w); res.append(status)
    if status=='ok': samples[str(d)]=(d,w,fit,ix)
s=pd.Series(res); print("R2MAX",R2MAX,"nights:",len(s), s.value_counts().to_dict())
print("ok: median length",np.median([f[1]-f[0]+1 for _,_,f,_ in samples.values()]),"bars; median height",np.median([f[2]-f[3] for _,_,f,_ in samples.values()]),"pts")
keys=['2024-05-27','2024-02-26','2026-02-13','2024-05-14','2024-07-16','2026-04-14','2025-09-22','2025-08-28']
rng=np.random.default_rng(int(R2MAX*100)); keys += list(rng.choice([k for k in samples if k not in keys],4,replace=False))
fig,axs=plt.subplots(3,4,figsize=(22,13))
for ax,k in zip(axs.flat,keys):
    d=pd.Timestamp(str(k)).date(); ix=days.get_group(d).to_numpy(); show=ix[(hm[ix]>=1800)|(hm[ix]<500)]; L=list(show)
    for x,j in enumerate(show):
        col='#26a69a' if c[j]>=o[j] else '#ef5350'
        ax.plot([x,x],[l[j],h[j]],color=col,lw=0.8); ax.plot([x,x],[o[j],c[j]],color=col,lw=3)
    ax.set_xticks([]); ax.set_facecolor('#111'); ax.tick_params(colors='w')
    if k in samples:
        _,w,(i,e,hh,ll),_=samples[k]; x0=L.index(w[i]); x1=L.index(w[e])
        ax.add_patch(plt.Rectangle((x0,ll),x1-x0,hh-ll,alpha=0.18,color='gold'))
        ax.axvline(L.index(w[-1]),color='gray',ls='--',lw=0.8)
        ax.set_title(f"{k}  box {e-i+1} bars, {hh-ll:.0f} pts",color='w')
    else:
        ax.set_title(f"{k}  no accumulation",color='orange')
fig.patch.set_facecolor('#111')
fig.suptitle(f"Accumulation v7 (no midline-cross rule) (gold): sideways candles, rotates through middle, no curve/trend shape (R2<= {R2MAX}). Top row = the 4 arcs from before.", color='w')
plt.tight_layout(); plt.savefig(f'accumulation_v7_{R2MAX}.png',dpi=80)
