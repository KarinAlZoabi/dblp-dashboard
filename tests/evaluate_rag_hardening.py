import json, statistics, sys, time
from collections import defaultdict
from urllib import request, error

API_URL = 'http://127.0.0.1:8000/api/rag/chat'

CASES = [
    # weird phrasing / paraphrases
    dict(name='weird_dataset_1',cat='weird',q='roughly speaking, how many publication records live in this DBLP dataset?',intent='dataset_count'),
    dict(name='weird_dataset_2',cat='weird',q="what's the total paper count in dblp?",intent='dataset_count'),
    dict(name='weird_authors',cat='weird',q="okay so who actually wrote 'Attention Is All You Need'?",intent='publication_authors',contains=['Ashish Vaswani']),
    dict(name='weird_pages',cat='weird',q="how long is 'Attention Is All You Need' in pages?",intent='publication_page_count',contains=['11']),
    dict(name='weird_venue',cat='weird',q="where did 'Attention Is All You Need' appear?",intent='publication_venue',contains=['NIPS','CoRR']),
    dict(name='weird_author_count',cat='weird',q="what's Kassem Danach's publication count?",intent='author_publication_count'),
    dict(name='weird_author_year',cat='weird',q='show me what Kassem Danach put out in 2020',intent='author_publications',years=(2020,2020)),
    dict(name='weird_topic',cat='weird',q="I'm looking for work on cyber attack detection using machine learning",intent='topic_search',min_sources=1),

    # capitalization / punctuation
    dict(name='caps_title',cat='formatting',q="WHO WROTE 'attention is all you need'???",intent='publication_authors',contains=['Ashish Vaswani']),
    dict(name='caps_topic',cat='formatting',q='FIND PAPERS ABOUT FEDERATED LEARNING',intent='topic_search',min_sources=1),
    dict(name='punct_author',cat='formatting',q='papers by... Kassem Danach?',intent='author_publications'),
    dict(name='punct_title',cat='formatting',q="page-count: 'Attention Is All You Need'?",intent='publication_page_count',contains=['11']),

    # typos - diagnostic WARNs
    dict(name='typo_title',cat='typos',q="Who wrote 'Attentin Is All You Need'?",intent='publication_authors',min_sources=1,warn=True),
    dict(name='typo_topic',cat='typos',q='find papers about federatd learnng',intent='topic_search',min_sources=1,warn=True),
    dict(name='typo_author',cat='typos',q='show publications by Kassem Danah',intent='author_publications',warn=True),
    dict(name='typo_keyword',cat='typos',q='papers on machin lerning for cyber attacks',intent='topic_search',min_sources=1,warn=True),

    # ranking / result count
    dict(name='latest_author',cat='ranking',q="What is Kassem Danach's most recent publication?",intent='author_publications',warn=True),
    dict(name='oldest_author',cat='ranking',q="What is Kassem Danach's earliest publication?",intent='author_publications',warn=True),
    dict(name='top3_topic',cat='ranking',q='Give me the top 3 papers about federated learning',intent='topic_search',min_sources=1,max_sources=3,warn=True),
    dict(name='top7_topic',cat='ranking',q='Show me 7 relevant papers on network intrusion detection',intent='topic_search',min_sources=1,max_sources=7,warn=True),

    # combined filters
    dict(name='author_range',cat='filters',q='Show all publications by Kassem Danach from 2015 to 2020',intent='author_publications',years=(2015,2020)),
    dict(name='author_year',cat='filters',q='What did Kassem Danach publish in 2020?',intent='author_publications',years=(2020,2020)),
    dict(name='topic_range',cat='filters',q='Find federated learning papers from 2020 to 2023',intent='topic_search',min_sources=1,years=(2020,2023)),
    dict(name='topic_year',cat='filters',q='Find network intrusion detection papers published in 2022',intent='topic_search',min_sources=1,years=(2022,2022)),
    dict(name='venue_filter',cat='filters',q='Find federated learning papers in CoRR from 2020 to 2023',intent='topic_search',warn=True),
    dict(name='type_filter',cat='filters',q='Find conference papers about federated learning from 2020 to 2023',intent='topic_search',warn=True),

    # missing / nonexistent
    dict(name='missing_author',cat='missing',q='Show papers by This Person Definitely Does Not Exist 9999',intent='author_publications',max_sources=0,contains=['could not find','not find','no publications']),
    dict(name='missing_title',cat='missing',q="Who wrote 'This Paper Definitely Does Not Exist In DBLP 123456'?",intent='publication_authors',max_sources=0,contains=['could not find','not find','no matching']),
    dict(name='missing_year',cat='missing',q='Show Kassem Danach publications in 1800',intent='author_publications',max_sources=0,warn=True),
    dict(name='missing_pages',cat='missing',q="What are the pages for 'This Paper Definitely Does Not Exist In DBLP 123456'?",intent='publication_pages',max_sources=0,warn=True),

    # ambiguity
    dict(name='ambiguous_author',cat='ambiguity',q='Show all publications by Hussein Hazimeh',intent='author_disambiguation',min_ids=2),
    dict(name='author_0001',cat='ambiguity',q='Show all publications by Hussein Hazimeh 0001',intent='author_publications'),
    dict(name='author_0002',cat='ambiguity',q='Show all publications by Hussein Hazimeh 0002',intent='author_publications'),
    dict(name='author_002',cat='ambiguity',q='Show all publications by Hussein Hazimeh 002',intent='author_publications'),
    dict(name='ambiguous_year',cat='ambiguity',q='What did Hussein Hazimeh publish in 2025?',intent='author_publications',warn=True),

    # malformed / unsupported
    dict(name='malformed_1',cat='malformed',q='papers???',warn=True),
    dict(name='malformed_2',cat='malformed',q='2023',warn=True),
    dict(name='malformed_3',cat='malformed',q='asdfghjkl qwertyuiop zxcvbnm',warn=True),
    dict(name='malformed_4',cat='malformed',q='tell me something',warn=True),

    # metadata
    dict(name='meta_year',cat='metadata',q="What year was 'Attention Is All You Need' published?",intent='publication_year',contains=['2017']),
    dict(name='meta_pages',cat='metadata',q="What is the page range for 'Attention Is All You Need'?",intent='publication_pages',contains=['5998','6008']),
    dict(name='meta_count',cat='metadata',q="How many pages does 'Attention Is All You Need' have?",intent='publication_page_count',contains=['11']),
    dict(name='meta_venue',cat='metadata',q="Which venue published 'Attention Is All You Need'?",intent='publication_venue',contains=['NIPS','CoRR']),
    dict(name='meta_details',cat='metadata',q="Tell me about 'Attention Is All You Need'",intent='publication_details',min_sources=1),

    # semantic spot checks
    dict(name='semantic_cyber',cat='semantic',q='Find research on machine learning techniques for detecting cyber attacks',intent='topic_search',min_sources=3,title_terms=['machine','cyber','attack','intrusion']),
    dict(name='semantic_federated',cat='semantic',q='Find papers about federated learning',intent='topic_search',min_sources=3,title_terms=['federated']),
    dict(name='semantic_graph',cat='semantic',q='Find papers about graph neural networks',intent='topic_search',min_sources=3,title_terms=['graph','neural']),
    dict(name='semantic_privacy',cat='semantic',q='Find research about privacy in federated learning',intent='topic_search',min_sources=2,title_terms=['privacy','federated']),
    dict(name='semantic_narrow',cat='semantic',q='Find papers about masked attention for graphs',intent='topic_search',min_sources=1,title_terms=['masked','attention','graph']),

    # counts
    dict(name='count_author',cat='counts',q='How many publications does Kassem Danach have?',intent='author_publication_count'),
    dict(name='count_author_year',cat='counts',q='How many publications did Kassem Danach have in 2020?',intent='author_publication_count'),
    dict(name='count_dataset',cat='counts',q='How many publication records are in this DBLP dataset?',intent='dataset_count'),
]

CHAINS = [
    ('chain_paper_facts', [
        ("Who wrote 'Attention Is All You Need'?",'publication_authors',None),
        ('Where did it appear?','publication_venue',None),
        ('How many pages is it?','publication_page_count',['11']),
        ('What year was that?','publication_year',['2017']),
    ]),
    ('chain_author_filters', [
        ('What did Kassem Danach publish in 2020?','author_publications',None),
        ('What about 2023?','author_publications',None),
        ('How many did they have that year?','author_publication_count',None),
    ]),
    ('chain_result_selection', [
        ('Find federated learning papers from 2020 to 2023','topic_search',None),
        ('Who wrote the second one?','publication_authors',None),
        ('Tell me about the newest one instead','publication_details',None),
    ]),
    ('chain_topic_refinement', [
        ('Find papers about federated learning','topic_search',None),
        ('What about privacy?','topic_search',None),
        ('Now only from 2020 to 2023','topic_search',None),
    ]),
]

def post(q,sid=None):
    req=request.Request(API_URL,data=json.dumps({'question':q,'top_k':5,'session_id':sid}).encode(),headers={'Content-Type':'application/json'},method='POST')
    t=time.perf_counter()
    try:
        with request.urlopen(req,timeout=120) as r:
            return json.loads(r.read().decode()),time.perf_counter()-t,None
    except error.HTTPError as e:
        return None,time.perf_counter()-t,f'HTTP {e.code}: {e.read().decode(errors="replace")}'
    except Exception as e:
        return None,time.perf_counter()-t,f'{type(e).__name__}: {e}'

def flat(x): return json.dumps(x,ensure_ascii=False).casefold()

def validate(c,r,e):
    f=[]
    if e:return [e]
    if r is None:return ['empty response']
    if c.get('intent') and r.get('intent')!=c['intent']:f.append(f"intent expected={c['intent']!r}, got={r.get('intent')!r}")
    src=r.get('sources') or []
    if c.get('min_sources') is not None and len(src)<c['min_sources']:f.append(f"sources expected >= {c['min_sources']}, got {len(src)}")
    if c.get('max_sources') is not None and len(src)>c['max_sources']:f.append(f"sources expected <= {c['max_sources']}, got {len(src)}")
    txt=flat(r)
    req=[x.casefold() for x in c.get('contains',[])]
    if req and not any(x in txt for x in req):f.append('missing all expected fragments: '+', '.join(c['contains']))
    if c.get('years') and src:
        lo,hi=c['years']; bad=[s.get('year') for s in src if s.get('year') is not None and not(lo<=s.get('year')<=hi)]
        if bad:f.append(f'years outside [{lo},{hi}]: {bad[:5]}')
    if c.get('title_terms') and src:
        terms=[x.casefold() for x in c['title_terms']]
        if not any(any(t in (s.get('title') or '').casefold() for t in terms) for s in src):f.append('no returned title contained relevance terms')
    if c.get('min_ids') is not None:
        ids=r.get('author_identities') or r.get('options') or []
        if len(ids)<c['min_ids']:f.append(f"author identities expected >= {c['min_ids']}, got {len(ids)}")
    if any((s.get('type') or '').casefold()=='www' for s in src):f.append('www/profile leak')
    return f

def main():
    print(f'Running {len(CASES)} adversarial DBLP tests...\n')
    results=[]
    for i,c in enumerate(CASES,1):
        r,lat,e=post(c['q']); f=validate(c,r,e); status='PASS' if not f else ('WARN' if c.get('warn') else 'FAIL')
        print(f"[{i:02d}/{len(CASES):02d}] {status:4} {lat:6.2f}s  {c['cat']:<12} {c['name']}")
        if f: print('    '+'; '.join(f))
        results.append(dict(case=c,status=status,latency=lat,failures=f,response=r,http_error=e))
    print('\nMULTI-TURN CHAINS\n'+'-'*80)
    chain_results=[]
    for name,turns in CHAINS:
        sid=None;fails=[];lats=[]
        for j,(q,intent,contains) in enumerate(turns,1):
            r,lat,e=post(q,sid);lats.append(lat)
            if e:fails.append(f'turn {j}: {e}');break
            sid=r.get('session_id') or sid
            if r.get('intent')!=intent:fails.append(f"turn {j} intent expected={intent!r}, got={r.get('intent')!r}")
            if contains and not any(x.casefold() in flat(r) for x in contains):fails.append(f"turn {j} missing expected {contains}")
        status='PASS' if not fails else 'FAIL';print(f'{status:4} {sum(lats):6.2f}s  {name}')
        for f in fails:print('    '+f)
        chain_results.append(dict(name=name,status=status,failures=fails,latencies=lats))
    hard=[x for x in results if x['status']=='FAIL'];warn=[x for x in results if x['status']=='WARN'];pas=[x for x in results if x['status']=='PASS'];cf=[x for x in chain_results if x['status']=='FAIL'];l=[x['latency'] for x in results]
    by=defaultdict(lambda:{'PASS':0,'WARN':0,'FAIL':0})
    for x in results:by[x['case']['cat']][x['status']]+=1
    print('\n'+'='*80+'\nHARDENING SUMMARY\n'+'='*80)
    print(f'Single-query PASS : {len(pas)}\nSingle-query WARN : {len(warn)}\nSingle-query FAIL : {len(hard)}\nConversation FAIL : {len(cf)}/{len(chain_results)}')
    print(f'Average latency   : {statistics.mean(l):.2f}s\nMedian latency    : {statistics.median(l):.2f}s\nMax latency       : {max(l):.2f}s')
    print('\nBy category:')
    for k,v in sorted(by.items()):print(f"  {k:<12} PASS={v['PASS']:<2} WARN={v['WARN']:<2} FAIL={v['FAIL']:<2}")
    with open('rag_hardening_report.json','w',encoding='utf-8') as fh:json.dump({'single_results':results,'chain_results':chain_results},fh,indent=2,ensure_ascii=False)
    print('\nDetailed report: rag_hardening_report.json')
    if hard or cf:sys.exit(1)

if __name__=='__main__':main()
