Vagrant.configure("2") do |config|
    # Check the host's architecture
    host_arch = `uname -m`.strip

    # Use a different box for ARM vs x86_64
    if host_arch == "arm64"
        # requires qemu, install qemu and then:
        # vagrant plugin install vagrant-qemu
        config.vm.box = "perk/ubuntu-24.04-arm64"
    else
        # Use the x86_64 compatible Ubuntu box
        config.vm.box = "ubuntu/jammy64"
    end

  config.vm.provider "qemu" do |qemu|
    qemu.memory = 2048
    qemu.cpus = 2
  end

  config.vm.provision "shell", path: "provision.sh"

  config.vm.synced_folder ".", "/home/vagrant/zfsdu", type: "rsync",
    rsync__exclude: [".git/", ".venv/"]
end
