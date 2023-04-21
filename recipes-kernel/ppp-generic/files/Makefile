obj-m := ppp_generic.o
obj-m += ppp_async.o
obj-m += ppp_deflate.o
obj-m += bsd_comp.o
obj-m += slhc.o
obj-m += crc-ccitt.o

SRC := $(shell pwd)

all:
	$(MAKE) -C $(KERNEL_SRC) M=$(SRC)

modules_install:
	$(MAKE) -C $(KERNEL_SRC) M=$(SRC) modules_install

clean:
	rm -f *.o *~ core .depend .*.cmd *.ko *.mod.c
	rm -f Module.markers Module.symvers modules.order
	rm -rf .tmp_versions Modules.symvers
