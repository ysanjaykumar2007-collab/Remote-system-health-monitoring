from os_ken.base import app_manager
from os_ken import cfg

if __name__ == "__main__":
    cfg.CONF(args=[], project="netpulse")

    print("[NETPULSE] Starting SDN Controller...")

    app_manager.AppManager.run_apps([
        "os_ken.controller.ofp_handler",
        "netpulse_controller"
    ])
