// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vregfile__pch.h"

//============================================================
// Constructors

Vregfile::Vregfile(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vregfile__Syms(contextp(), _vcname__, this)}
    , clock{vlSymsp->TOP.clock}
    , reset{vlSymsp->TOP.reset}
    , val{vlSymsp->TOP.val}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Vregfile::Vregfile(const char* _vcname__)
    : Vregfile(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vregfile::~Vregfile() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vregfile___024root___eval_debug_assertions(Vregfile___024root* vlSelf);
#endif  // VL_DEBUG
void Vregfile___024root___eval_static(Vregfile___024root* vlSelf);
void Vregfile___024root___eval_initial(Vregfile___024root* vlSelf);
void Vregfile___024root___eval_settle(Vregfile___024root* vlSelf);
void Vregfile___024root___eval(Vregfile___024root* vlSelf);

void Vregfile::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vregfile::eval_step\n"); );
#ifdef VL_DEBUG
    // Debug assertions
    Vregfile___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_deleter.deleteAll();
    if (VL_UNLIKELY(!vlSymsp->__Vm_didInit)) {
        vlSymsp->__Vm_didInit = true;
        VL_DEBUG_IF(VL_DBG_MSGF("+ Initial\n"););
        Vregfile___024root___eval_static(&(vlSymsp->TOP));
        Vregfile___024root___eval_initial(&(vlSymsp->TOP));
        Vregfile___024root___eval_settle(&(vlSymsp->TOP));
    }
    VL_DEBUG_IF(VL_DBG_MSGF("+ Eval\n"););
    Vregfile___024root___eval(&(vlSymsp->TOP));
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

//============================================================
// Events and timing
bool Vregfile::eventsPending() { return false; }

uint64_t Vregfile::nextTimeSlot() {
    VL_FATAL_MT(__FILE__, __LINE__, "", "No delays in the design");
    return 0;
}

//============================================================
// Utilities

const char* Vregfile::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

void Vregfile___024root___eval_final(Vregfile___024root* vlSelf);

VL_ATTR_COLD void Vregfile::final() {
    Vregfile___024root___eval_final(&(vlSymsp->TOP));
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vregfile::hierName() const { return vlSymsp->name(); }
const char* Vregfile::modelName() const { return "Vregfile"; }
unsigned Vregfile::threads() const { return 1; }
void Vregfile::prepareClone() const { contextp()->prepareClone(); }
void Vregfile::atClone() const {
    contextp()->threadPoolpOnClone();
}
