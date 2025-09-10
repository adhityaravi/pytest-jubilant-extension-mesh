#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Service mesh extension for pytest-jubilant."""

import json
import pathlib
from pathlib import Path
from typing import Dict, Any

try:
    import jubilant
    from pytest_jubilant_extension_meta import BaseExtension
    
    class MeshExtension(BaseExtension):
        """Service mesh extension for pytest-jubilant using Istio components."""
        
        @property
        def name(self) -> str:
            return "mesh"
        
        
        @property
        def help_text(self) -> str:
            return "Add mesh components to the test and operate under meshed condition"
        
        def setup_infrastructure(self, temp_model_factory) -> None:
            """Setup Istio service mesh infrastructure."""
            # Get main juju instance and setup beacon
            juju = temp_model_factory.get_juju("")
            juju.deploy(
                charm="istio-beacon-k8s",
                app="istio-beacon-k8s",
                channel="2/edge",
                config={"model-on-mesh": "true"}
            )
            
            # Setup Istio in separate model
            istio = temp_model_factory.get_juju("istio-system")
            istio.deploy(
                charm="istio-k8s",
                app="istio-k8s",
                channel="2/edge",
            )
            
            # Mark juju as mesh-enabled.
            juju.mesh_enabled = True
            
            # Wait for deployments
            juju.wait(jubilant.all_active)
            istio.wait(jubilant.all_active)
        
        def modify_deploy_args(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
            """Enable trust for mesh deployments."""
            kwargs = kwargs.copy()
            kwargs['trust'] = True
            return kwargs
        
        def post_deploy_hook(self, juju, app: str, charm) -> None:
            """Auto-integrate mesh-capable apps to istio beacon."""
            
            app = app or self._get_charm_name(charm)

            if not hasattr(juju, 'mesh_enabled') or not juju.mesh_enabled:
                return
                
            if self._mesh_endpoint_exists(juju, app):
                self._integrate_to_beacon(juju, app)
        
        def _mesh_endpoint_exists(self, juju, app: str) -> bool:
            """Check if app has service-mesh endpoint."""
            try:
                stdout = juju.cli("show-application", app, "--format", "json")
                app_properties = json.loads(stdout)
                endpoint_bindings = app_properties[app]["endpoint-bindings"]
                return "service-mesh" in endpoint_bindings
            except Exception:
                return False
        
        def _integrate_to_beacon(self, juju, app: str):
            """Integrate app to istio beacon."""
            juju.integrate(f"{app}:service-mesh", "istio-beacon-k8s:service-mesh")
        
        def _get_charm_name(self, charm: str | Path) -> str:
            """Extract charm name from path for .charm files."""
            if not str(charm).endswith(".charm"):
                return str(charm)
            
            charm_file = Path(charm).stem
            return charm_file.rsplit('_', 1)[0]

except ImportError:
    # Dependencies not available
    class MeshExtension:
        def __init__(self):
            raise ImportError(
                "Mesh extension requires additional dependencies. "
                "Install with: pip install pytest-jubilant-extension-mesh"
            )
