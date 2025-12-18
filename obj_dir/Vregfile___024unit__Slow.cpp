// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vregfile.h for the primary calling header

#include "Vregfile__pch.h"
#include "Vregfile__Syms.h"
#include "Vregfile___024unit.h"

void Vregfile___024unit___ctor_var_reset(Vregfile___024unit* vlSelf);

Vregfile___024unit::Vregfile___024unit(Vregfile__Syms* symsp, const char* v__name)
    : VerilatedModule{v__name}
    , vlSymsp{symsp}
 {
    // Reset structure values
    Vregfile___024unit___ctor_var_reset(this);
}

void Vregfile___024unit::__Vconfigure(bool first) {
    (void)first;  // Prevent unused variable warning
}

Vregfile___024unit::~Vregfile___024unit() {
}
