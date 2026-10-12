"""1NFER public discovery MCP; optional LOCAL stdio procurement with saved keys."""
import argparse,importlib.util,json,os,re,secrets,threading,time
from decimal import Decimal,InvalidOperation
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
spec=importlib.util.spec_from_file_location('infer_client',Path(__file__).with_name('infer_client.py'));client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
CACHE={};LOCK=threading.Lock()
def public(path):
 with LOCK:
  old=CACHE.get(path)
  if old and time.monotonic()-old[0]<60:return old[1]
  value=client.Client().request(path);CACHE[path]=(time.monotonic(),value);return value

def estimate(model,input_tokens,output_tokens,factor=1):
 if type(input_tokens)!=int or type(output_tokens)!=int or not 0<=input_tokens<=1000000 or not 0<=output_tokens<=128000:raise ValueError('Invalid token counts')
 rows=public('/v1/models').get('data',[]);row=next((r for r in rows if r.get('id')==model),None)
 if row is None:raise ValueError('Use an exact live model identifier')
 pricing=row.get('pricing',{});ip=pricing.get('input_per_1m_usd');op=pricing.get('output_per_1m_usd')
 # Never invent a missing rate or infer a tier from nominal balance.
 if ip is None or op is None:return {'estimate_available':False,'model':model,'reason':'Live public per-million rates unavailable; inspect authenticated account rates.'}
 cost=(Decimal(str(ip))*input_tokens+Decimal(str(op))*output_tokens)/1000000
 if not cost.is_finite() or cost<0:raise ValueError('Invalid live rates')
 return {'estimate_available':True,'model':model,'reference_usd':format(cost,'.8f'),'discount_assumed':False,'estimate_only':True,'actual_usage_and_account_rates_apply':True}

def create(local=False):
 app=FastMCP('1NFER inference discovery',host='127.0.0.1',port=18085,stateless_http=True,json_response=True,transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,allowed_hosts=['127.0.0.1:*','localhost:*','1nfer.net'],allowed_origins=['https://1nfer.net']))
 @app.tool(annotations={'readOnlyHint':True,'destructiveHint':False,'openWorldHint':True})
 def list_models()->dict:
  """Read exact available model identifiers and public reference rates; no generation or charge."""
  return public('/v1/models')
 @app.tool(annotations={'readOnlyHint':True,'destructiveHint':False,'openWorldHint':True})
 def payment_terms()->dict:
  """Read currently enabled currencies, minimum funding and payment conditions; no invoice or transfer."""
  return public('/v1/payments/terms')
 @app.tool(annotations={'readOnlyHint':True,'destructiveHint':False,'openWorldHint':True})
 def estimate_cost(model:str,input_tokens:int,output_tokens:int)->dict:
  """Estimate from live public rates without calling a model; no account discount assumed."""
  return estimate(model,input_tokens,output_tokens)
 @app.tool(annotations={'readOnlyHint':True,'destructiveHint':False,'openWorldHint':False})
 def connection_recipe(framework:str)->dict:
  """Get inspectable first-party setup instructions; does not install, sign up or spend."""
  paths={'opencode':'https://1nfer.net/downloads/setup-opencode.py','openwebui':'https://1nfer.net/guides/crypto-inference-agents.html','continue':'https://1nfer.net/guides/crypto-inference-agents.html','python':'https://1nfer.net/guides/crypto-inference-agents.html'}
  if framework not in paths:raise ValueError('Supported: opencode, openwebui, continue, python')
  return {'framework':framework,'base_url':'https://1nfer.net/v1','guide':paths[framework],'signup':'https://1nfer.net/?utm_source=mcp&utm_medium=tool&utm_campaign='+framework,'business':'https://1nfer.net/guides/launch-your-service.html','key_requirement':'Save your own key privately before registration. Never send it to this public MCP.','no_free_model':True,'full_framework_runtime_verified':False,'tools_route_previously_verified':'claude-sonnet-4-6','responses_supported':False}
 if local:
  directory=Path(os.environ.get('INFER_STATE_DIR',str(Path.home()/'.config/1nfer-client')));directory.mkdir(parents=True,exist_ok=True,mode=0o700)
  if directory.is_symlink() or directory.stat().st_uid!=os.getuid() or directory.stat().st_mode&0o077:raise ValueError('Local state must be private and owned by you')
  keyfile=directory/'key.private.json'
  def own():return client.Client(client.key_read(keyfile))
  def sanitized(value):return json.loads(client.KEY.sub('[private key]',json.dumps(value)))
  @app.tool(annotations={'readOnlyHint':False,'destructiveHint':False,'idempotentHint':True,'openWorldHint':True})
  def register_account(referral_code:str='')->dict:
   """LOCAL ONLY. Save a key locally then register it. No invoice, payment or inference. Reuses saved key."""
   if referral_code and not client.ACCOUNT.fullmatch(referral_code):raise ValueError('Invalid public referral code')
   if not keyfile.exists():client.private_write(keyfile,{'api_key':'hs-live-'+secrets.token_hex(32),'referral_code':referral_code or None})
   saved=client.private_read(keyfile)
   if (saved.get('referral_code') or '')!=referral_code:raise ValueError('Saved registration has another referral; preserve original')
   value=own().register(saved.get('referral_code'))
   return {'registered':True,'account_id':value.get('account_id'),'key_saved_locally':True,'key_returned':False}
  @app.tool(annotations={'readOnlyHint':True,'destructiveHint':False,'openWorldHint':True})
  def account_status()->dict:
   """LOCAL ONLY. Read your account using the privately saved key; key never returned."""
   return sanitized(own().request('/v1/account',private=True))
  @app.tool(annotations={'readOnlyHint':False,'destructiveHint':False,'idempotentHint':True,'openWorldHint':True})
  def create_invoice(credit_usd:str,asset:str,intent_id:str,authorized_max_usd:str)->dict:
   """LOCAL ONLY. Create a crypto invoice within the authorized budget. No wallet execution or payment."""
   if not re.fullmatch(r'[A-Za-z0-9_-]{8,48}',intent_id):raise ValueError('Use a saved 8–48 character intent identifier')
   credit=Decimal(client.amount(credit_usd));cap=Decimal(client.amount(authorized_max_usd))
   terms=public('/v1/payments/terms');fee=Decimal(str(terms.get('processing_fee_usd','NaN')))
   if not fee.is_finite() or fee<0:raise ValueError('Verified fee unavailable; inspect live terms')
   if credit+fee>cap:raise ValueError('Exceeds authorized budget including service fee')
   return sanitized(own().topup(str(credit),directory/(intent_id+'.invoice.private.json'),asset))
  @app.tool(annotations={'readOnlyHint':True,'destructiveHint':False,'openWorldHint':True})
  def invoice_status(invoice_id:str)->dict:
   """LOCAL ONLY. Read a saved public invoice identity. No payment replay or generation."""
   if not re.fullmatch(r'inv_[A-Za-z0-9_-]{32}',invoice_id):raise ValueError('Invalid invoice identifier')
   return sanitized(client.Client().request('/v1/invoices/'+invoice_id))
 return app
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stdio',action='store_true');a=p.parse_args();create(local=a.stdio).run(transport='stdio' if a.stdio else 'streamable-http')
