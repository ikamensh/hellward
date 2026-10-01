// Injected into Godot for captures (tools/godot-capture.sh): the app never becomes active, never takes
// keyboard focus and shows no Dock icon, so rendering frames does not disturb whoever is using the Mac.
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
// The capture window never draws (scenes/capture.tscn renders offscreen), so it is shown fully transparent,
// click-through and out of the window cycle: nothing for the person at the Mac to see or hit.
static void show_invisibly(NSWindow *w) {
    w.alphaValue = 0.0;
    w.ignoresMouseEvents = YES;
    w.hasShadow = NO;
    w.collectionBehavior = NSWindowCollectionBehaviorStationary | NSWindowCollectionBehaviorIgnoresCycle;
    [w orderBack:nil];
}
static void order_front_quietly(id self, SEL _cmd, id sender) { show_invisibly((NSWindow *)self); }

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
    replace([NSWindow class], @"makeKeyAndOrderFront:", (IMP)order_front_quietly);
    replace([NSWindow class], @"orderFront:", (IMP)order_front_quietly);
    replace([NSWindow class], @"makeKeyWindow", (IMP)ignore);
    replace([NSWindow class], @"makeMainWindow", (IMP)ignore);
}
