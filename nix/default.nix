{ lib
, python311Packages
, pkgs
}:

let
  # Define the Python packages required
  pythonPackages = pkgs.python311.withPackages (ps: with ps; [
    numpy
    libevdev
    xlib
    pyinotify
    smbus2
    pyasyncore
    pywayland
    xkbcommon
    systemd
  ]);
in
python311Packages.buildPythonPackage {
  pname = "asus-dialpad-driver";
  version = "0.0.1";
  src = ../.;

  format = "other";

  propagatedBuildInputs = with pkgs; [
    ibus
    libevdev
    curl
    xorg.xinput
    i2c-tools
    libxml2
    libxkbcommon
    libgcc
    gcc
    pythonPackages  # Python dependencies already include python311
  ];

  doCheck = false;

  # Skip build and just focus on copying files, no setuptools required
  buildPhase = ''
    echo "Skipping build phase since there's no setup.py"
  '';

  # Install files for driver and layouts
  installPhase = ''
    mkdir -p $out/share/asus-dialpad-driver

    # Copy the driver script
    cp dialpad.py $out/share/asus-dialpad-driver/

    # Copy layouts directory if it exists, and remove __pycache__ if present
    if [ -d layouts ]; then
      cp -r layouts $out/share/asus-dialpad-driver/
      rm -rf $out/share/asus-dialpad-driver/layouts/__pycache__
    fi
  '';

  meta = {
    homepage = "https://github.com/asus-linux-drivers/asus-dialpad-driver";
    description = "Linux driver for DialPad on Asus laptops.";
    license = lib.licenses.gpl2;
    platforms = lib.platforms.linux;
    maintainers = with lib.maintainers; [asus-linux-drivers];
    mainProgram = "dialpad.py";
  };
}