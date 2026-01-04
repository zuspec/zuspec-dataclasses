.. Zuspec Language documentation master file, created by
   sphinx-quickstart on Fri Aug 29 02:05:59 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Zuspec Language
===============

Zuspec is a Python-embedded multi-abstraction language for modeling 
hardware - from the transfer-function level down to RTL. 

Version: 2026.1 (January 2026)

**Quick Links:**

* `API Reference <../API_REFERENCE.md>`_ - Complete API documentation (154 elements)
* `README <../README.md>`_ - Quick start guide
* `Parameterization Guide <../PARAMETERIZATION_SUMMARY.md>`_ - Const fields and lambda expressions
* :doc:`checker` - IR Checker and flake8 integration (NEW!)
* `Profile System <profiles.html>`_ - Platform-specific abstraction levels

.. toctree::
   :maxdepth: 2
   :caption: User Guide:

   intro
   components
   fields
   types
   runtime
   abstraction_levels
   checker

.. toctree::
   :maxdepth: 2
   :caption: Advanced Topics:

   datamodel
   profiles
   
.. toctree::
   :maxdepth: 1
   :caption: Additional Documentation:
   
   RTL_QUICKSTART

.. toctree::
   :maxdepth: 1
   :caption: Historical Documentation (Deprecated):
   
   profile_checker_guide
   profile_checker_design

.. note::
   The mypy-based profile checker (profile_checker_guide) is deprecated as of version 2026.1.
   Use the new flake8-based IR checker instead (see :doc:`checker`).

