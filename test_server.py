import asyncio,importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import server as s
class Discovery(unittest.IsolatedAsyncioTestCase):
 async def test_public_has_no_private_procurement(self):
  names={x.name for x in await s.create().list_tools()}
  self.assertEqual(names,{'list_models','payment_terms','estimate_cost','connection_recipe'})
 async def test_local_has_real_procurement_and_preserves_key(self):
  with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'INFER_STATE_DIR':root}):
   app=s.create(local=True);names={x.name for x in await app.list_tools()}
   self.assertIn('create_invoice',names)
   with patch.object(s.client.Client,'register',return_value={'account_id':'key_ABCDEFGH'}):
    result=await app.call_tool('register_account',{})
    before=(Path(root)/'key.private.json').read_bytes()
    again=await app.call_tool('register_account',{})
    self.assertEqual(before,(Path(root)/'key.private.json').read_bytes())
    self.assertNotIn('hs-live-',str(result));self.assertNotIn('hs-live-',str(again))
 async def test_cost_missing_rates_does_not_invent(self):
  with patch.object(s,'public',return_value={'data':[{'id':'a'}]}):self.assertFalse(s.estimate('a',1,1)['estimate_available'])
 async def test_cost_decimal_and_invalid_tokens(self):
  with patch.object(s,'public',return_value={'data':[{'id':'a','pricing':{'input_per_1m_usd':2,'output_per_1m_usd':10}}]}):
   self.assertEqual(s.estimate('a',1000,100)['reference_usd'],'0.00300000')
   for n in [-1,True,1000001]:
    with self.assertRaises(ValueError):s.estimate('a',n,1)
 async def test_invoice_budget_rejects_before_topup(self):
  with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'INFER_STATE_DIR':root}):
   app=s.create(local=True)
   with patch.object(s,'public',return_value={'processing_fee_usd':'0.00'}),patch.object(s.client.Client,'topup') as topup:
    with self.assertRaises(Exception):await app.call_tool('create_invoice',{'credit_usd':'20','asset':'XMR','intent_id':'test_intent','authorized_max_usd':'1'})
    topup.assert_not_called()
if __name__=='__main__':unittest.main()
