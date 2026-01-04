import asyncio
import zuspec.dataclasses as zdc

def test_tlm_channel():

    @zdc.dataclass
    class Prod(zdc.Component):
        p : zdc.PutIF[int] = zdc.port()

        async def _send(self):
            for i in range(16):
                await self.p.put(i)
                await self.wait(zdc.Time.ns(10))

    @zdc.dataclass
    class Cons(zdc.Component):
        c : zdc.GetIF[int] = zdc.port()

        @zdc.process
        async def _recv(self):
            while True:
                i = await self.c.get()
                print("Received %d" % i)

    @zdc.dataclass
    class Top(zdc.Component):
        p : Prod = zdc.field()
        c : Cons = zdc.field()
        ch : zdc.Channel[int] = zdc.field()

        def __bind__(self): return {
            self.p.p : self.ch.put,
            self.c.c : self.ch.get
        }

    t = Top()

    asyncio.run(t.p._send())


def test_tlm_channel_struct():
    """Test TLM channel with struct (dataclass) types."""
    
    @zdc.dataclass
    class Transaction:
        """A simple transaction struct."""
        addr : int = zdc.field(default=0)
        data : int = zdc.field(default=0)
        write : bool = zdc.field(default=False)

    received_transactions = []

    @zdc.dataclass
    class Producer(zdc.Component):
        p : zdc.PutIF[Transaction] = zdc.port()

        async def send_transactions(self):
            for i in range(8):
                txn = Transaction(addr=0x1000 + i*4, data=i*0x11, write=(i % 2 == 0))
                await self.p.put(txn)
                await self.wait(zdc.Time.ns(10))

    @zdc.dataclass
    class Consumer(zdc.Component):
        c : zdc.GetIF[Transaction] = zdc.port()

        @zdc.process
        async def recv_transactions(self):
            while True:
                txn = await self.c.get()
                received_transactions.append(txn)
                print(f"Received: addr={txn.addr:#x}, data={txn.data:#x}, write={txn.write}")

    @zdc.dataclass
    class Top(zdc.Component):
        prod : Producer = zdc.field()
        cons : Consumer = zdc.field()
        ch : zdc.Channel[Transaction] = zdc.field()

        def __bind__(self): return {
            self.prod.p : self.ch.put,
            self.cons.c : self.ch.get
        }

    t = Top()
    asyncio.run(t.prod.send_transactions())
    
    # Verify we received all transactions
    assert len(received_transactions) == 8, f"Expected 8 transactions, got {len(received_transactions)}"
    
    # Verify transaction contents
    for i, txn in enumerate(received_transactions):
        assert txn.addr == 0x1000 + i*4, f"Transaction {i} addr mismatch"
        assert txn.data == i*0x11, f"Transaction {i} data mismatch"
        assert txn.write == (i % 2 == 0), f"Transaction {i} write mismatch"
    
    print("All struct transactions verified successfully")
    t.shutdown()


def test_tlm_channel_try_methods():
    """Test non-blocking try_put and try_get methods."""
    
    @zdc.dataclass
    class Top(zdc.Component):
        ch : zdc.Channel[int] = zdc.field()

        async def run(self):
            # Test try_get on empty channel
            success, val = self.ch.get.try_get()
            assert not success, "try_get should fail on empty channel"
            
            # Test try_put
            success = self.ch.put.try_put(42)
            assert success, "try_put should succeed"
            
            # Test try_get on non-empty channel
            success, val = self.ch.get.try_get()
            assert success, "try_get should succeed on non-empty channel"
            assert val == 42, f"Expected 42, got {val}"
            
            # Test try_get again on empty channel
            success, val = self.ch.get.try_get()
            assert not success, "try_get should fail on empty channel again"
            
            print("try_put/try_get tests passed")

    t = Top()
    asyncio.run(t.run())
    t.shutdown()


def test_tlm_channel_datamodel():
    """Test that TLM Channel types are properly represented in the datamodel."""
    import zuspec.dataclasses.ir as dm

    @zdc.dataclass
    class Producer(zdc.Component):
        p : zdc.PutIF[int] = zdc.port()

    @zdc.dataclass
    class Consumer(zdc.Component):
        c : zdc.GetIF[int] = zdc.port()

    @zdc.dataclass
    class Top(zdc.Component):
        prod : Producer = zdc.field()
        cons : Consumer = zdc.field()
        ch : zdc.Channel[int] = zdc.field()

        def __bind__(self): return {
            self.prod.p : self.ch.put,
            self.cons.c : self.ch.get
        }

    dm_ctxt = zdc.DataModelFactory().build(Top)

    # Verify Top is in the context
    top_qualname = Top.__qualname__
    assert top_qualname in dm_ctxt.type_m, f"Top ({top_qualname}) should be in context"
    
    top_dm = dm_ctxt.type_m[top_qualname]
    assert isinstance(top_dm, dm.DataTypeComponent), \
        f"Top should be DataTypeComponent, got {type(top_dm).__name__}"

    # Verify Top has three fields: prod, cons, ch
    field_names = {f.name for f in top_dm.fields}
    assert 'prod' in field_names, "Top should have 'prod' field"
    assert 'cons' in field_names, "Top should have 'cons' field"
    assert 'ch' in field_names, "Top should have 'ch' field"

    # Find the ch field and verify its type
    ch_field = None
    for f in top_dm.fields:
        if f.name == 'ch':
            ch_field = f
            break
    
    assert ch_field is not None, "ch field should exist"
    assert isinstance(ch_field.datatype, dm.DataTypeChannel), \
        f"ch field should be DataTypeChannel, got {type(ch_field.datatype).__name__}"

    # Verify Producer is in the context
    prod_qualname = Producer.__qualname__
    assert prod_qualname in dm_ctxt.type_m, f"Producer ({prod_qualname}) should be in context"
    
    prod_dm = dm_ctxt.type_m[prod_qualname]
    assert isinstance(prod_dm, dm.DataTypeComponent), \
        f"Producer should be DataTypeComponent, got {type(prod_dm).__name__}"

    # Find the p field in Producer and verify its type
    p_field = None
    for f in prod_dm.fields:
        if f.name == 'p':
            p_field = f
            break
    
    assert p_field is not None, "p field should exist in Producer"
    assert isinstance(p_field.datatype, dm.DataTypePutIF), \
        f"p field should be DataTypePutIF, got {type(p_field.datatype).__name__}"
    assert p_field.kind == dm.FieldKind.Port, \
        f"p field should be Port kind, got {p_field.kind}"

    # Verify Consumer is in the context
    cons_qualname = Consumer.__qualname__
    assert cons_qualname in dm_ctxt.type_m, f"Consumer ({cons_qualname}) should be in context"
    
    cons_dm = dm_ctxt.type_m[cons_qualname]
    assert isinstance(cons_dm, dm.DataTypeComponent), \
        f"Consumer should be DataTypeComponent, got {type(cons_dm).__name__}"

    # Find the c field in Consumer and verify its type
    c_field = None
    for f in cons_dm.fields:
        if f.name == 'c':
            c_field = f
            break
    
    assert c_field is not None, "c field should exist in Consumer"
    assert isinstance(c_field.datatype, dm.DataTypeGetIF), \
        f"c field should be DataTypeGetIF, got {type(c_field.datatype).__name__}"
    assert c_field.kind == dm.FieldKind.Port, \
        f"c field should be Port kind, got {c_field.kind}"

    print("TLM Channel datamodel test passed")


def test_tlm_channel_struct_datamodel():
    """Test that TLM Channel with struct types is properly represented in the datamodel."""
    import zuspec.dataclasses.ir as dm

    @zdc.dataclass
    class Transaction:
        addr : int = zdc.field(default=0)
        data : int = zdc.field(default=0)

    @zdc.dataclass
    class Top(zdc.Component):
        ch : zdc.Channel[Transaction] = zdc.field()

    dm_ctxt = zdc.DataModelFactory().build(Top)

    # Verify Top is in the context
    top_qualname = Top.__qualname__
    assert top_qualname in dm_ctxt.type_m, f"Top ({top_qualname}) should be in context"
    
    top_dm = dm_ctxt.type_m[top_qualname]

    # Find the ch field and verify its type
    ch_field = None
    for f in top_dm.fields:
        if f.name == 'ch':
            ch_field = f
            break
    
    assert ch_field is not None, "ch field should exist"
    assert isinstance(ch_field.datatype, dm.DataTypeChannel), \
        f"ch field should be DataTypeChannel, got {type(ch_field.datatype).__name__}"
    
    # Verify the element type is captured
    assert ch_field.datatype.element_type is not None, \
        "Channel element_type should not be None"

    print("TLM Channel struct datamodel test passed")


