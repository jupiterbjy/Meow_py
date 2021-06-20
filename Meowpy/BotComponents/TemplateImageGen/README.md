## Template Image combiner

![image](https://user-images.githubusercontent.com/26041217/122682801-836da500-d236-11eb-8deb-488985c9856b.png)

---

### Usage

Using `template_under.png` and `template_upper.png`, sandwiches user's *profile image* or *attached image*.

```shell
# (Assuming prefix //)

//template [margin_percent=0.0] [background=True]

Attach image to frame it, or user's profile image will be framed. Set margin in percent to add padding.
```

First parameter sets margin percentage. This adds padding to image, or zoom in image when negative value is passed.

Second parameter sets background visibility. If false, will not add `template_under.png` (but still is required) to final image.

---

### Warning

- `template_under.png` `template_upper.png` need to be in same width and height.
- `template_under.png` `template_upper.png` need to be present. If only using one of them, then set other as blank image.


---
### Example 1:

- No attachment
- margine -20(zoom 20%)
- background-less
    
![image](https://user-images.githubusercontent.com/26041217/122682569-3fc66b80-d235-11eb-9a27-f2c59c0c2fa4.png)


---
### Example 2:

- Image attached
- margine 10(padding 10%)
- background enabled [Default]

![image](https://user-images.githubusercontent.com/26041217/122682614-7ac89f00-d235-11eb-91cc-ce0418577153.png)
