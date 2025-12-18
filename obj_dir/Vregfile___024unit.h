// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vregfile.h for the primary calling header

#ifndef VERILATED_VREGFILE___024UNIT_H_
#define VERILATED_VREGFILE___024UNIT_H_  // guard

#include "verilated.h"


class Vregfile__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vregfile___024unit final : public VerilatedModule {
  public:

    // INTERNAL VARIABLES
    Vregfile__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vregfile___024unit(Vregfile__Syms* symsp, const char* v__name);
    ~Vregfile___024unit();
    VL_UNCOPYABLE(Vregfile___024unit);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
