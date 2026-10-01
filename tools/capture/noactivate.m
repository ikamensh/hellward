// Injected into Godot for captures (tools/godot-capture.sh): the app never becomes active, never takes keyboard
// focus, never puts a window on screen and shows no Dock icon, so rendering does not disturb whoever uses the Mac.
#import <AppKit/AppKit.h>
#import <objc/runtime.h>

static BOOL keep_accessory(id self, SEL _cmd, NSApplicationActivationPolicy policy) {
    // the original setter, applied with the accessory policy whatever Godot asked for
    static BOOL (*original)(id, SEL, NSApplicationActivationPolicy);
    if (!original) {
        original = (BOOL (*)(id, SEL, NSApplicationActivationPolicy))
            method_getImplementation(class_getInstanceMethod([NSApplication class], NSSelectorFromString(@"hw_setActivationPolicy:")));
    }
    return original(self, _cmd, NSApplicationActivationPolicyAccessory);
}

static void ignore(id self, SEL _cmd, ...) {}
static BOOL ignore_bool(id self, SEL _cmd, ...) { return NO; }
// The capture window never draws (scenes/capture.tscn renders offscreen), so it is never put on screen at all:
// ordering a window in, even behind others, can pull the person at the Mac to the desktop Space.
static void order_out(id self, SEL _cmd, ...) {}
static void (*original_order)(id, SEL, NSWindowOrderingMode, NSInteger);
static void order_window(id self, SEL _cmd, NSWindowOrderingMode mode, NSInteger other) {
    if (mode == NSWindowOut) original_order(self, _cmd, mode, other);   // taking a window away is fine
}

static void replace(Class cls, NSString *name, IMP imp) {
    Method m = class_getInstanceMethod(cls, NSSelectorFromString(name));
    if (m) method_setImplementation(m, imp);
}

// Godot never sets an activation policy, so a bundled app starts as a regular Dock app: set the accessory
// policy as soon as the application object exists, before it finishes launching and shows a Dock tile.
static id (*original_shared)(id, SEL);
static id shared_as_accessory(id self, SEL _cmd) {
    id app = original_shared(self, _cmd);
    static BOOL done = NO;
    if (!done) {
        done = YES;
        keep_accessory(app, @selector(setActivationPolicy:), NSApplicationActivationPolicyAccessory);
    }
    return app;
}

__attribute__((constructor)) static void install(void) {
    Class app = [NSApplication class];
    Method set = class_getInstanceMethod(app, @selector(setActivationPolicy:));
    class_addMethod(app, NSSelectorFromString(@"hw_setActivationPolicy:"), method_getImplementation(set), method_getTypeEncoding(set));
    method_setImplementation(set, (IMP)keep_accessory);
    Method shared = class_getClassMethod(app, @selector(sharedApplication));
    original_shared = (id (*)(id, SEL))method_getImplementation(shared);
    method_setImplementation(shared, (IMP)shared_as_accessory);
    replace(app, @"activateIgnoringOtherApps:", (IMP)ignore);
    replace(app, @"activate", (IMP)ignore);
    replace([NSRunningApplication class], @"activateWithOptions:", (IMP)ignore_bool);
    replace([NSWindow class], @"makeKeyAndOrderFront:", (IMP)order_out);
    replace([NSWindow class], @"orderFront:", (IMP)order_out);
    replace([NSWindow class], @"orderFrontRegardless", (IMP)order_out);
    replace([NSWindow class], @"orderBack:", (IMP)order_out);
    Method order = class_getInstanceMethod([NSWindow class], @selector(orderWindow:relativeTo:));
    original_order = (void (*)(id, SEL, NSWindowOrderingMode, NSInteger))method_getImplementation(order);
    method_setImplementation(order, (IMP)order_window);
    replace([NSWindow class], @"toggleFullScreen:", (IMP)order_out);
    replace([NSWindow class], @"makeKeyWindow", (IMP)ignore);
    replace([NSWindow class], @"makeMainWindow", (IMP)ignore);
}
