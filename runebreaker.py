#!/usr/bin/env python3
"""Rune Decryptor helper: multilingual monoalphabetic substitution solver.

Supports: de, en, es, fr, grc, it, la, nl, ru, sv

Usage:
  python rune_decryptor.py analyze cipher.txt
  python rune_decryptor.py solve cipher.txt --corpora corpora --top 5
  python rune_decryptor.py solve cipher.txt --language sv --corpora corpora
  python rune_decryptor.py nearby cipher.txt mapping.json --corpora corpora --correct 18 --total 20

For best results, create corpora/en.txt, corpora/de.txt, ... corpora/grc.txt
with a few MB of representative public-domain prose per language.
"""
from __future__ import annotations
import argparse, itertools, json, math, random, re, sys, unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple, List

LANGUAGES = ("de","en","es","fr","grc","it","la","nl","ru","sv")
NAMES = {"de":"German","en":"English","es":"Spanish","fr":"French","grc":"Ancient Greek","it":"Italian","la":"Latin","nl":"Dutch","ru":"Russian","sv":"Swedish"}
ALPHABETS = {
 "de":"abcdefghijklmnopqrstuvwxyz","en":"abcdefghijklmnopqrstuvwxyz","es":"abcdefghijklmnopqrstuvwxyz",
 "fr":"abcdefghijklmnopqrstuvwxyz","it":"abcdefghijklmnopqrstuvwxyz","la":"abcdefghijklmnopqrstuvwxyz",
 "nl":"abcdefghijklmnopqrstuvwxyz","sv":"abcdefghijklmnopqrstuvwxyz",
 "ru":"абвгдежзийклмнопрстуфхцчшщъыьэюя","grc":"αβγδεζηθικλμνξοπρστυφχψω",
}
FREQ = {
 "en":"etaoinshrdlucmfwypvbgkjqxz","de":"enisratdhulcgmobwfkzpvjyxq",
 "es":"eaosrnidlctumpbgvyqhfzjxkw","fr":"esaitnrulodcmpvqfbghjxykwz",
 "it":"eaionlrtscdpumgvfbqzhxjkyw","la":"eituasnroclmdpqugbvfhxyzkjw",
 "nl":"enairtodslgvhmkpubcwfjzyxq","sv":"eantrslidomgkvhufbpcywjxqz",
 "ru":"оеаинтсрвлкмдпуяызьгбчйхжшюцщэфъ","grc":"αεοτινρσλκμηπυδγβθωχφξψζ",
}
COMMON = {
 "en":"the of and to in a is that for it as was with be by on not he i this are or his from at which but have an had they you were their one all we can her has there been if more when will would who what so no".split(),
 "de":"der die und in den von zu das mit sich des auf fur ist im dem nicht ein eine als auch es an werden aus er hat dass sie nach wird bei einer um am sind noch wie einem uber einen so zum war haben nur".split(),
 "es":"de la que el en y a los del se las por un para con no una su al lo como mas pero sus le ya o este si porque esta entre cuando muy sin sobre tambien me hasta hay donde quien desde todo nos durante todos".split(),
 "fr":"de la le et les des en un une du que a pour dans qui sur pas plus par au avec ce il elle se son sa aux ne comme mais ou nous vous leur ses est sont avait cette entre tout quand sans".split(),
 "it":"di che e la il un a per in una del non le si da al con lo come piu dei gli era ma o alla ha nel su anche se nella questo tra sono lui sua tutto essere".split(),
 "la":"et in est non ut cum ad de qui quae quod ex per sed si sunt esse aut ab quam hoc haec ille illa eius atque neque enim etiam autem se ea eum eos nobis vos".split(),
 "nl":"de het een en van in is dat op te voor met zijn niet aan er als ook die bij maar om uit was hij zij naar heeft deze over door tot ik je dit worden nog".split(),
 "sv":"och i att det som en pa ar av for med den till inte ett han hon de sig var om men sa har hade fran man skulle dar nar vid eller efter under kan allt".split(),
 "ru":"и в не на я быть он с что а по это она этот к но они мы как из у который то за свой весь год от так о для ты же все тот мочь вы человек такой его сказать только или еще бы себя один как".split(),
 "grc":"και δε τε γαρ ου ο η το του την των εν ει ως προς απο δια επι αλλα μεν ουκ εστι ειναι αυτου αυτην αυτο τον τω τη".split(),
}
ONE = {"en":{"a","i"},"de":set(),"es":{"a","o","y"},"fr":{"a","y"},"it":{"a","e","o"},"la":{"a","e","o"},"nl":set(),"sv":{"i"},"ru":{"а","в","и","к","о","с","у","я"},"grc":{"ο","η"}}
PUNCT=set(".,;:!?-'\"()[]{}<>/\\|@#$%^&*_+=~`…—–")

def strip_marks(s):
    return ''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')

def norm(text, lang):
    text=strip_marks(text.lower())
    if lang=='grc': text=text.replace('ς','σ')
    elif lang!='ru':
        text=(text.replace('ß','ss').replace('æ','ae').replace('œ','oe').replace('ø','o').replace('å','a').replace('ä','a').replace('ö','o'))
    A=set(ALPHABETS[lang]); return ''.join(c for c in text if c in A)

def words_norm(text, lang):
    text=strip_marks(text.lower())
    if lang=='grc': text=text.replace('ς','σ')
    elif lang!='ru': text=(text.replace('ß','ss').replace('æ','ae').replace('œ','oe').replace('ø','o').replace('å','a').replace('ä','a').replace('ö','o'))
    return re.findall(f"[{re.escape(ALPHABETS[lang])}]+", text)

def issym(ch):
    if ch.isspace() or ch in PUNCT: return False
    cat=unicodedata.category(ch)
    return not (cat.startswith('P') or cat.startswith('Z'))

def symbols(ct):
    out=[]
    for c in ct:
        if issym(c) and c not in out: out.append(c)
    return out

def cipher_words(ct):
    out=[]; cur=[]
    for c in ct:
        if issym(c): cur.append(c)
        elif cur: out.append(''.join(cur)); cur=[]
    if cur: out.append(''.join(cur))
    return out

def decrypt(ct,key,unknown='?'):
    return ''.join(key.get(c,unknown) if issym(c) else c for c in ct)

def pattern(w):
    m={}; nxt=0; out=[]
    for c in w:
        if c not in m: m[c]=nxt; nxt+=1
        out.append(m[c])
    return tuple(out)

def patstr(w):
    alpha='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    return ''.join(alpha[i] if i<len(alpha) else str(i) for i in pattern(w))

def analyze(ct):
    sy=symbols(ct); ws=cipher_words(ct); sf=Counter(c for c in ct if issym(c)); wf=Counter(ws); total=sum(sf.values())
    print(f"Cipher symbols: {len(sy)}\nWord tokens: {len(ws)}\nUnique words: {len(wf)}\n")
    print('SYMBOL FREQUENCY')
    for s,n in sf.most_common(): print(f"  {s} {n:4d} {100*n/total:6.2f}%")
    print('\nMOST COMMON WORDS')
    for w,n in wf.most_common(30): print(f"  {w:<20} {n:3d} len={len(w):2d} pattern={patstr(w)}")
    print('\nONE-LETTER WORDS')
    ow=Counter(w for w in ws if len(w)==1)
    print('  '+(', '.join(f'{w}:{n}' for w,n in ow.most_common()) if ow else '(none)'))

class NGram:
    def __init__(self, corpus, lang, n):
        self.lang=lang; self.n=n; t=norm(corpus,lang)
        cnt=Counter(t[i:i+n] for i in range(max(0,len(t)-n+1))); self.total=sum(cnt.values())
        if not self.total: raise ValueError(f'no usable {n}-grams for {lang}')
        self.log={g:math.log(c/self.total) for g,c in cnt.items()}; self.floor=math.log(0.05/self.total)
    def score(self,text):
        t=norm(text,self.lang)
        if len(t)<self.n: return -1e12
        return sum(self.log.get(t[i:i+self.n],self.floor) for i in range(len(t)-self.n+1))

@dataclass
class Model:
    lang:str; tri:NGram; quad:NGram; wc:Counter
    def score(self,text):
        chars=norm(text,self.lang)
        if not chars: return -1e12
        s=.45*self.tri.score(text)/len(chars)+self.quad.score(text)/len(chars)
        ws=words_norm(text,self.lang); common=set(COMMON[self.lang]); bonus=pen=0.0
        for w in ws:
            if w in common: bonus += min(7,len(w))*.30
            c=self.wc.get(w,0)
            if c: bonus += min(2.5,math.log1p(c)*.08)
            if len(w)==1 and w not in ONE[self.lang]: pen += 1.5
        if ws: s += bonus/len(ws)-pen/len(ws)
        return s

def fallback(lang): return (" ".join(COMMON[lang])+" ")*100

def load_model(lang,corpdir):
    p=corpdir/f'{lang}.txt'
    if p.exists(): corpus=p.read_text(encoding='utf-8',errors='ignore')
    else:
        print(f'[warning] {p} missing; using tiny fallback profile',file=sys.stderr); corpus=fallback(lang)
    return Model(lang,NGram(corpus,lang,3),NGram(corpus,lang,4),Counter(words_norm(corpus,lang)))

def init_key(ct,lang):
    sy=symbols(ct); A=ALPHABETS[lang]
    if len(sy)>len(A): raise ValueError(f'{len(sy)} symbols > {len(A)}-letter alphabet')
    cf=Counter(c for c in ct if c in sy); co=[c for c,_ in cf.most_common()]
    po=[]
    for p in FREQ[lang]+A:
        q=norm(p,lang)
        if len(q)==1 and q in A and q not in po: po.append(q)
    return {c:p for c,p in zip(co,po)}

def parse_fixed(items):
    out={}
    for x in items or []:
        if '=' not in x: raise ValueError(f'bad --fix {x!r}')
        a,b=x.split('=',1)
        if len(a)!=1 or len(b)!=1: raise ValueError('--fix must be rune=letter')
        out[a]=b
    if len(set(out.values()))!=len(out): raise ValueError('fixed plaintext letters must be unique')
    return out

def apply_fixed(key,fixed):
    key=dict(key)
    for c,p in fixed.items():
        if c not in key: raise ValueError(f'{c!r} absent from ciphertext')
        other=next((x for x,v in key.items() if v==p),None)
        if other is None: key[c]=p
        elif other!=c: key[c],key[other]=key[other],key[c]
    return key

def randomize(key,n=100):
    k=dict(key); sy=list(k)
    for _ in range(n):
        a,b=random.sample(sy,2); k[a],k[b]=k[b],k[a]
    return k

@dataclass
class Result:
    lang:str; score:float; key:Dict[str,str]; plaintext:str

def anneal(ct,model,key,fixed,steps,temp0=1.5,temp1=.01):
    k=dict(key); mutable=[c for c in k if c not in fixed]; cur=model.score(decrypt(ct,k)); best=cur; bk=dict(k)
    if len(mutable)<2:return best,bk
    cool=(temp1/temp0)**(1/max(1,steps-1)); temp=temp0
    for _ in range(steps):
        a,b=random.sample(mutable,2); k[a],k[b]=k[b],k[a]
        sc=model.score(decrypt(ct,k)); d=sc-cur
        if d>=0 or random.random()<math.exp(d/max(temp,1e-12)):
            cur=sc
            if sc>best: best=sc; bk=dict(k)
        else: k[a],k[b]=k[b],k[a]
        temp*=cool
    return best,bk

def solve_lang(ct,lang,model,restarts,steps,fixed,seed=None):
    if seed is not None: random.seed(seed)
    base=apply_fixed(init_key(ct,lang),fixed); best=-math.inf; bk=base
    for r in range(1,restarts+1):
        k=apply_fixed(randomize(base,50+r*3),fixed); sc,cand=anneal(ct,model,k,fixed,steps)
        if sc>best: best=sc; bk=cand
        print(f'[{lang}] {r:3d}/{restarts} best={best: .5f}  {decrypt(ct,bk).replace(chr(10)," ")[:100]}')
    return Result(lang,best,bk,decrypt(ct,bk))

def save_mapping(path,res):
    path.write_text(json.dumps({'language':res.lang,'score':res.score,'mapping':res.key},ensure_ascii=False,indent=2),encoding='utf-8')

def load_mapping(path):
    d=json.loads(path.read_text(encoding='utf-8')); return d.get('language'),dict(d.get('mapping',d))

def print_result(r):
    print(f'\n{r.lang} ({NAMES[r.lang]}) score={r.score:.6f}\n{"-"*72}\n{r.plaintext}\n\nMAPPING')
    for c,p in sorted(r.key.items(),key=lambda kv:kv[1]): print(f'  {c} -> {p}')

def neighbors(key,max_swaps):
    sy=list(key)
    for a,b in itertools.combinations(sy,2):
        k=dict(key); k[a],k[b]=k[b],k[a]; yield k
    if max_swaps>=2:
        pairs=list(itertools.combinations(sy,2)); seen=set()
        for (a,b),(c,d) in itertools.combinations(pairs,2):
            k=dict(key); k[a],k[b]=k[b],k[a]; k[c],k[d]=k[d],k[c]
            sig=tuple(sorted(k.items()))
            if sig not in seen: seen.add(sig); yield k

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('analyze'); a.add_argument('ciphertext')
    s=sub.add_parser('solve'); s.add_argument('ciphertext'); s.add_argument('--corpora',type=Path,default=Path('corpora')); s.add_argument('--language',choices=LANGUAGES); s.add_argument('--restarts',type=int,default=30); s.add_argument('--steps',type=int,default=40000); s.add_argument('--top',type=int,default=5); s.add_argument('--seed',type=int); s.add_argument('--fix',action='append'); s.add_argument('--save',type=Path)
    n=sub.add_parser('nearby'); n.add_argument('ciphertext'); n.add_argument('mapping',type=Path); n.add_argument('--corpora',type=Path,default=Path('corpora')); n.add_argument('--language',choices=LANGUAGES); n.add_argument('--correct',type=int); n.add_argument('--total',type=int); n.add_argument('--max-swaps',type=int,choices=(1,2)); n.add_argument('--top',type=int,default=20)
    args=ap.parse_args(); ct=sys.stdin.read() if args.ciphertext=='-' else Path(args.ciphertext).read_text(encoding='utf-8')
    if args.cmd=='analyze': analyze(ct); return
    if args.cmd=='solve':
        fixed=parse_fixed(args.fix); langs=[args.language] if args.language else list(LANGUAGES); results=[]
        for lang in langs:
            if len(symbols(ct))>len(ALPHABETS[lang]): print(f'Skip {lang}: alphabet too small'); continue
            print('\n'+'='*72+f'\n{lang}: {NAMES[lang]}\n'+'='*72)
            try: results.append(solve_lang(ct,lang,load_model(lang,args.corpora),args.restarts,args.steps,fixed,args.seed))
            except ValueError as e: print(f'Skip {lang}: {e}')
        results.sort(key=lambda r:r.score,reverse=True)
        print('\n\nRANKED RESULTS\n'+'#'*72)
        for r in results[:args.top]: print_result(r)
        if args.save and results: save_mapping(args.save,results[0]); print(f'\nSaved {args.save}')
        return
    lang0,key=load_mapping(args.mapping); lang=args.language or lang0
    if not lang: raise SystemExit('Specify --language (not stored in mapping).')
    model=load_model(lang,args.corpora); maxsw=args.max_swaps
    if maxsw is None and args.correct is not None and args.total is not None: maxsw=1 if args.total-args.correct<=2 else 2 if args.total-args.correct<=4 else 1
    maxsw=maxsw or 1; scored=[Result(lang,model.score(decrypt(ct,key)),dict(key),decrypt(ct,key))]
    for k in neighbors(key,maxsw): scored.append(Result(lang,model.score(decrypt(ct,k)),k,decrypt(ct,k)))
    scored.sort(key=lambda r:r.score,reverse=True)
    for r in scored[:args.top]: print_result(r)

if __name__=='__main__': main()
