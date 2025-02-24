
inputs: { config, lib, pkgs, ... }:

let
  cfg = config.services.asus-dialpad-driver;
  defaultPackage = inputs.self.packages.${pkgs.system}.default;

  # Function to convert configuration options to string
  toConfigFile = cfg: builtins.concatStringsSep "\n" (
    [ "[main]" ] ++ lib.attrsets.mapAttrsToList (key: value: "${key} = ${value}") cfg.config
  );

  # Writable directory for the config file
  configDir = "/etc/asus-dialpad-driver/";
in {
  options.services.asus-dialpad-driver = {
    enable = lib.mkEnableOption "Enable the Asus DialPad Driver service.";

    layout = lib.mkOption {
      type = lib.types.str;
      default = "proart16";
      description = "The layout identifier for the DialPad driver (e.g. proart16). This value is required.";
    };

    wayland = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable this option to run under Wayland. Disable it for X11.";
    };

    waylandDisplay = lib.mkOption {
      type = lib.types.str;
      default = "wayland-0";
      description = "The WAYLAND_DISPLAY environment variable. Default is wayland-0.";
    };

    runtimeDir = lib.mkOption {
      type = lib.types.str;
      default = "/run/user/1000/";
      description = "The XDG_RUNTIME_DIR environment variable, specifying the runtime directory.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ defaultPackage ];

    # Ensure the writable directories exists
    systemd.tmpfiles.rules = [
      "d ${configDir} 0755 root root -"
      "d /var/log/asus-dialpad-driver 0755 root root -"
    ];

    # Enable i2c
    hardware.i2c.enable = true;

    # Add groups for dialpad
    users.groups = {
      uinput = { };
      input = { };
      i2c = { };
    };

    # Add root to the necessary groups
    users.users.root.extraGroups = [ "i2c" "input" "uinput" ];

    # Add the udev rule to set permissions for uinput and i2c-dev
    services.udev.extraRules = ''
      # Set uinput device permissions
      KERNEL=="uinput", GROUP="uinput", MODE="0660"
      # Set i2c-dev permissions
      SUBSYSTEM=="i2c-dev", GROUP="i2c", MODE="0660"
    '';

    # Load specific kernel modules
    boot.kernelModules = [ "uinput" "i2c-dev" ];

    systemd.services.asus-dialpad-driver = {
      description = "Asus DialPad Driver";
      wantedBy = [ "default.target" ];
      startLimitBurst=20;
      startLimitIntervalSec=300;
      serviceConfig = {
        Type = "simple";
        ExecStart = "${defaultPackage}/share/asus-dialpad-driver/dialpad.py ${cfg.layout}";
        StandardOutput = null;
        StandardError = null;
        Restart = "on-failure";
        RestartSec = 1;
        TimeoutSec = 5;
        WorkingDirectory = "${defaultPackage}";
        Environment = [
          ''XDG_SESSION_TYPE=${if cfg.wayland then "wayland" else "x11"}''
          ''XDG_RUNTIME_DIR=${cfg.runtimeDir}''
          ''WAYLAND_DISPLAY=${cfg.waylandDisplay}''
        ];
      };
    };

  };
}
